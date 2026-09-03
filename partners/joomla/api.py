import re
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urlsplit, urlunsplit

import httpx

from partners.models import ArticleSnapshot
from partners.services.page_renderer import has_managed_marker
from .base import JoomlaAdapter
from .exceptions import (
    JoomlaArticleError,
    JoomlaAuthenticationError,
    JoomlaConnectionError,
    JoomlaPermissionError,
    ManagedMarkerMismatch,
)


READMORE_RE = re.compile(
    r"<hr\b(?=[^>]*\bid\s*=\s*['\"]system-readmore['\"])[^>]*>",
    re.IGNORECASE,
)
READMORE_HTML = '<hr id="system-readmore" />'


@dataclass(frozen=True)
class JoomlaApiArticle:
    article_id: int
    title: str
    alias: str
    body_html: str


class JoomlaApiAdapter(JoomlaAdapter):
    user_agent = "JoomlaPartnersControl/1.0"

    @property
    def api_base_url(self):
        explicit = self.donor.api_url.strip()
        if explicit:
            value = explicit.rstrip("/")
        else:
            admin = urlsplit(self.donor.admin_url)
            root_path = admin.path.split("/administrator", 1)[0].rstrip("/")
            value = urlunsplit(
                (
                    admin.scheme,
                    admin.netloc,
                    f"{root_path}/api/index.php/v1",
                    "",
                    "",
                )
            )

        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise JoomlaConnectionError(f"Некорректный Joomla API URL: {value}")
        return value

    def _headers(self):
        if self.donor.auth_mode != "api_token":
            raise JoomlaAuthenticationError(
                f"Для Joomla {self.version} выберите способ авторизации API Token"
            )
        token = self.api_token().strip()
        if not token:
            raise JoomlaAuthenticationError("API Token Joomla не задан")
        return {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/json",
            "X-Joomla-Token": token,
            "User-Agent": self.user_agent,
        }

    def _http_transport(self):
        return None

    def _http_client(self):
        kwargs = {
            "follow_redirects": False,
            "timeout": httpx.Timeout(20.0, connect=10.0),
            "headers": self._headers(),
        }
        transport = self._http_transport()
        if transport is not None:
            kwargs["transport"] = transport
        return httpx.Client(**kwargs)

    @staticmethod
    def _error_detail(response):
        try:
            payload = response.json()
        except ValueError:
            payload = None

        details = []
        if isinstance(payload, dict):
            for error in payload.get("errors", []):
                if not isinstance(error, dict):
                    continue
                detail = error.get("detail") or error.get("title")
                if detail:
                    details.append(str(detail))
        if not details:
            text = response.text.strip()
            if text:
                details.append(text)
        return "; ".join(details)[:500]

    def _request(self, client, method, path, **kwargs):
        url = f"{self.api_base_url}/{path.lstrip('/')}"
        try:
            response = client.request(method, url, **kwargs)
        except (httpx.HTTPError, OSError) as exc:
            raise JoomlaConnectionError(
                f"Ошибка HTTP при обращении к Joomla {self.version} API: {exc}"
            ) from exc

        detail = self._error_detail(response)
        token = client.headers.get("X-Joomla-Token", "")
        if token:
            detail = detail.replace(token, "[REDACTED]")
        suffix = f": {detail}" if detail else ""
        if 300 <= response.status_code < 400:
            raise JoomlaConnectionError(
                f"Joomla API вернул redirect {response.status_code}. "
                f"Укажите конечный HTTPS API URL без перенаправления{suffix}"
            )
        if response.status_code == 401:
            raise JoomlaAuthenticationError(
                "Joomla API отклонил X-Joomla-Token. Проверьте токен и плагин "
                f"API Authentication - Web Services Joomla Token{suffix}"
            )
        if response.status_code == 403:
            raise JoomlaPermissionError(
                "Joomla API запретил операцию. Пользователю нужны core.login.api "
                f"и права просмотра/создания/редактирования материалов{suffix}"
            )
        if response.status_code == 404:
            raise JoomlaArticleError(
                f"Joomla API endpoint или материал не найден{suffix}"
            )
        if response.status_code >= 400:
            raise JoomlaArticleError(
                f"Joomla API отклонил запрос ({response.status_code}){suffix}"
            )
        return response

    @staticmethod
    def _json(response):
        try:
            payload = response.json()
        except ValueError as exc:
            raise JoomlaArticleError("Joomla API вернул некорректный JSON") from exc
        if not isinstance(payload, dict):
            raise JoomlaArticleError("Joomla API вернул неожиданный формат JSON")
        return payload

    @classmethod
    def _article_from_resource(cls, resource):
        if not isinstance(resource, dict):
            raise JoomlaArticleError("Joomla API не вернул объект материала")
        attributes = resource.get("attributes")
        if not isinstance(attributes, dict):
            attributes = {}

        raw_id = resource.get("id") or attributes.get("id")
        try:
            article_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise JoomlaArticleError("Joomla API не вернул ID материала") from exc

        articletext = attributes.get("articletext")
        if articletext is None:
            introtext = attributes.get("introtext") or ""
            fulltext = attributes.get("fulltext") or ""
            articletext = (
                f"{introtext}{READMORE_HTML}{fulltext}"
                if fulltext
                else introtext
            )
        return JoomlaApiArticle(
            article_id=article_id,
            title=str(attributes.get("title") or ""),
            alias=str(attributes.get("alias") or ""),
            body_html=str(articletext or ""),
        )

    @classmethod
    def _article_from_response(cls, response):
        payload = cls._json(response)
        data = payload.get("data")
        if isinstance(data, list):
            if not data:
                raise JoomlaArticleError("Joomla API вернул пустой список материалов")
            data = data[0]
        return cls._article_from_resource(data)

    @classmethod
    def _article_id_from_response(cls, response):
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict):
            raw_id = data.get("id")
            attributes = data.get("attributes")
            if not raw_id and isinstance(attributes, dict):
                raw_id = attributes.get("id")
            try:
                return int(raw_id)
            except (TypeError, ValueError):
                pass

        location = response.headers.get("Location", "")
        match = re.search(r"/(\d+)/?$", location)
        return int(match.group(1)) if match else None

    @staticmethod
    def _alias_from_response(response, fallback):
        try:
            payload = response.json()
        except ValueError:
            return fallback
        data = payload.get("data") if isinstance(payload, dict) else None
        attributes = data.get("attributes") if isinstance(data, dict) else None
        if isinstance(attributes, dict):
            return str(attributes.get("alias") or fallback)
        return fallback

    @staticmethod
    def _split_article_text(html):
        parts = READMORE_RE.split(html, maxsplit=1)
        return parts[0], parts[1] if len(parts) == 2 else ""

    def _save_snapshot(self, article, reason):
        return ArticleSnapshot.objects.create(
            donor=self.donor,
            article_id=article.article_id,
            title=article.title,
            body_html=article.body_html,
            body_hash=sha256(article.body_html.encode()).hexdigest(),
            reason=reason,
        )

    def _get_article(self, client, article_id):
        response = self._request(
            client,
            "GET",
            f"content/articles/{int(article_id)}",
        )
        article = self._article_from_response(response)
        if article.article_id != int(article_id):
            raise JoomlaArticleError(
                f"Joomla API вернул материал #{article.article_id} вместо #{article_id}"
            )
        return article

    def _patch_article(self, client, article_id, html):
        introtext, fulltext = self._split_article_text(html)
        return self._request(
            client,
            "PATCH",
            f"content/articles/{int(article_id)}",
            json={
                "id": int(article_id),
                "introtext": introtext,
                "fulltext": fulltext,
            },
        )

    def test_connection(self):
        with self._http_client() as client:
            if self.donor.article_id:
                article = self._get_article(client, self.donor.article_id)
                return (
                    f"Joomla {self.version} API: token принят, "
                    f"материал #{article.article_id} доступен — {article.title}"
                )
            self._request(
                client,
                "GET",
                "content/articles",
                params={"page[limit]": 1},
            )
            return f"Joomla {self.version} API: token принят, список материалов доступен"

    def get_article(self, article_id):
        with self._http_client() as client:
            return self._get_article(client, article_id)

    def create_article(self, alias="", html="", title=None, category_id=None, **kwargs):
        title = (title or self.donor.article_title or "Наши партнёры").strip()
        category_id = category_id or self.donor.article_category_id or 2
        alias = alias or self.donor.article_alias
        if not title:
            raise JoomlaArticleError("Для создания материала не задан заголовок")

        with self._http_client() as client:
            response = self._request(
                client,
                "POST",
                "content/articles",
                json={
                    "title": title,
                    "alias": alias,
                    "articletext": html,
                    "catid": int(category_id),
                    "state": 1,
                    "language": "*",
                    "metadesc": "",
                    "metakey": "",
                },
            )
            article_id = self._article_id_from_response(response)
            if not article_id:
                raise JoomlaArticleError(
                    "Joomla API создал материал без определяемого ID; "
                    "автоматическая привязка остановлена"
                )

            saved_alias = self._alias_from_response(response, alias)
            self.donor.article_id = article_id
            update_fields = ["article_id", "updated_at"]
            if saved_alias and saved_alias != self.donor.article_alias:
                self.donor.article_alias = saved_alias
                update_fields.append("article_alias")
            self.donor.save(update_fields=update_fields)

            verified = self._get_article(client, article_id)
            if not has_managed_marker(verified.body_html, self.donor):
                raise JoomlaArticleError(
                    f"Материал #{article_id} создан и привязан к донору, "
                    "но managed-marker после записи не найден; "
                    "дальнейшая синхронизация остановлена"
                )
            return (
                f"Материал #{article_id} создан через Joomla {self.version} API "
                "и принят под управление JPC"
            )

    def adopt_article(self, article_id):
        with self._http_client() as client:
            article = self._get_article(client, article_id)
            expected = (
                f"<!-- JPC-MANAGED-PAGE:{self.donor.managed_marker_uuid} -->"
            )
            if expected in article.body_html:
                return f"Материал #{article_id} уже находится под управлением JPC"
            if "<!-- JPC-MANAGED-PAGE:" in article.body_html:
                raise ManagedMarkerMismatch(
                    "Материал содержит marker другого донора JPC"
                )

            snapshot = self._save_snapshot(article, "before_adoption")
            self._patch_article(
                client,
                article_id,
                expected + "\n" + article.body_html,
            )
            verified = self._get_article(client, article_id)
            if not has_managed_marker(verified.body_html, self.donor):
                raise JoomlaArticleError(
                    "Joomla API не сохранил managed-marker; "
                    "исходный HTML сохранён в snapshot"
                )
            return (
                f"Материал #{article_id} принят под управление; "
                f"backup snapshot #{snapshot.pk}"
            )

    def update_article(self, article_id, html):
        with self._http_client() as client:
            article = self._get_article(client, article_id)
            if not has_managed_marker(article.body_html, self.donor):
                raise ManagedMarkerMismatch(
                    "Публикация запрещена: managed-marker материала не совпадает. "
                    "Сначала выполните принятие под управление."
                )

            snapshot = self._save_snapshot(article, "before_update")
            self._patch_article(client, article_id, html)
            verified = self._get_article(client, article_id)
            if not has_managed_marker(verified.body_html, self.donor):
                raise JoomlaArticleError(
                    f"Проверка после записи не пройдена; "
                    f"backup snapshot #{snapshot.pk}"
                )
            return (
                f"Материал #{article_id} обновлён через Joomla {self.version} API; "
                f"backup snapshot #{snapshot.pk}"
            )
