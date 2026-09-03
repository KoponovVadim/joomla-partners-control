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


@dataclass(frozen=True)
class JoomlaConnectorArticle:
    article_id: int
    title: str
    alias: str
    body_html: str


class Joomla3ConnectorAdapter(JoomlaAdapter):
    version = "3"
    user_agent = "JoomlaPartnersControl/1.0"
    connector_protocol = 1

    @property
    def connector_url(self):
        explicit = self.donor.connector_url.strip()
        if explicit:
            value = explicit
        else:
            admin = urlsplit(self.donor.admin_url)
            root_path = admin.path.split("/administrator", 1)[0].rstrip("/")
            value = urlunsplit(
                (
                    admin.scheme,
                    admin.netloc,
                    f"{root_path}/index.php",
                    "option=com_ajax&plugin=jpcconnector&format=raw",
                    "",
                )
            )

        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise JoomlaConnectionError(
                f"Некорректный JPC Connector URL: {value}"
            )
        return value

    def _headers(self):
        if self.donor.auth_mode != "connector_token":
            raise JoomlaAuthenticationError(
                "Для этого подключения выберите JPC Connector (Joomla 3)"
            )
        token = self.connector_token().strip()
        if len(token) < 32:
            raise JoomlaAuthenticationError(
                "JPC Connector Token не задан или короче 32 символов"
            )
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-JPC-Token": token,
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
    def _response_detail(response):
        try:
            payload = response.json()
        except ValueError:
            text = response.text.strip()
            return text[:500] if text else ""

        if isinstance(payload, dict):
            return str(
                payload.get("error")
                or payload.get("message")
                or ""
            )[:500]
        return ""

    def _command(self, client, action, **payload):
        body = {
            "protocol": self.connector_protocol,
            "action": action,
            **payload,
        }
        try:
            response = client.post(self.connector_url, json=body)
        except (httpx.HTTPError, OSError) as exc:
            raise JoomlaConnectionError(
                f"Ошибка HTTP при обращении к JPC Connector: {exc}"
            ) from exc

        detail = self._response_detail(response)
        token = client.headers.get("X-JPC-Token", "")
        if token:
            detail = detail.replace(token, "[REDACTED]")
        suffix = f": {detail}" if detail else ""

        if 300 <= response.status_code < 400:
            raise JoomlaConnectionError(
                "JPC Connector вернул redirect. Укажите конечный HTTPS URL "
                f"без перенаправления{suffix}"
            )
        if response.status_code == 401:
            raise JoomlaAuthenticationError(
                f"JPC Connector отклонил token{suffix}"
            )
        if response.status_code == 403:
            raise JoomlaPermissionError(
                f"JPC Connector запретил операцию{suffix}"
            )
        if response.status_code == 404:
            raise JoomlaArticleError(
                f"JPC Connector или материал не найден{suffix}"
            )
        if response.status_code == 409:
            raise JoomlaArticleError(
                f"JPC Connector обнаружил конфликт записи{suffix}"
            )
        if response.status_code >= 400:
            raise JoomlaArticleError(
                f"JPC Connector вернул HTTP {response.status_code}{suffix}"
            )

        try:
            result = response.json()
        except ValueError as exc:
            raise JoomlaConnectionError(
                "Сайт не вернул JSON JPC Connector. Проверьте, что плагин "
                "установлен, включён и URL не перехватывается защитой хостинга."
            ) from exc
        if not isinstance(result, dict):
            raise JoomlaConnectionError(
                "JPC Connector вернул неожиданный формат JSON"
            )
        if not result.get("ok"):
            raise JoomlaArticleError(
                "JPC Connector отклонил запрос"
                + (f": {detail}" if detail else "")
            )
        data = result.get("data")
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _article(data):
        try:
            article_id = int(data["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise JoomlaArticleError(
                "JPC Connector не вернул ID материала"
            ) from exc
        return JoomlaConnectorArticle(
            article_id=article_id,
            title=str(data.get("title") or ""),
            alias=str(data.get("alias") or ""),
            body_html=str(data.get("body_html") or ""),
        )

    def _get_article(self, client, article_id):
        article = self._article(
            self._command(
                client,
                "get",
                article_id=int(article_id),
            )
        )
        if article.article_id != int(article_id):
            raise JoomlaArticleError(
                f"JPC Connector вернул материал #{article.article_id} "
                f"вместо #{article_id}"
            )
        return article

    def _save_snapshot(self, article, reason):
        return ArticleSnapshot.objects.create(
            donor=self.donor,
            article_id=article.article_id,
            title=article.title,
            body_html=article.body_html,
            body_hash=sha256(article.body_html.encode()).hexdigest(),
            reason=reason,
        )

    def _write_and_verify(
        self,
        client,
        action,
        article_id,
        html,
        **payload,
    ):
        """Treat a failed write response as success only if Joomla stored it."""
        try:
            self._command(
                client,
                action,
                article_id=int(article_id),
                html=html,
                **payload,
            )
        except JoomlaArticleError as write_error:
            try:
                verified = self._get_article(client, article_id)
            except Exception:
                raise write_error
            if verified.body_html != html:
                raise write_error
            return verified, True

        return self._get_article(client, article_id), False

    def test_connection(self):
        with self._http_client() as client:
            info = self._command(client, "ping")
            connector = info.get("connector_version", "unknown")
            joomla = info.get("joomla_version", "3")
            if self.donor.article_id:
                article = self._get_article(client, self.donor.article_id)
                return (
                    f"JPC Connector {connector}, Joomla {joomla}: "
                    f"материал #{article.article_id} доступен — {article.title}"
                )
            return (
                f"JPC Connector {connector}: подключение выполнено, "
                f"Joomla {joomla}"
            )

    def get_article(self, article_id):
        with self._http_client() as client:
            return self._get_article(client, article_id)

    def create_article(
        self,
        alias="",
        html="",
        title=None,
        category_id=None,
        **kwargs,
    ):
        title = (title or self.donor.article_title or "Наши партнёры").strip()
        category_id = category_id or self.donor.article_category_id or 2
        alias = alias or self.donor.article_alias
        if not title:
            raise JoomlaArticleError(
                "Для создания материала не задан заголовок"
            )
        if not has_managed_marker(html, self.donor):
            raise ManagedMarkerMismatch(
                "Создание запрещено: в новом материале отсутствует "
                "managed-marker текущего донора"
            )

        marker = str(self.donor.managed_marker_uuid)
        with self._http_client() as client:
            created = self._command(
                client,
                "create",
                title=title,
                alias=alias,
                category_id=int(category_id),
                html=html,
                marker_uuid=marker,
            )
            article = self._article(created)

            # The remote article already exists. Persist its identity before
            # marker verification so a retry cannot create a duplicate.
            self.donor.article_id = article.article_id
            update_fields = ["article_id", "updated_at"]
            if article.alias and article.alias != self.donor.article_alias:
                self.donor.article_alias = article.alias
                update_fields.append("article_alias")
            self.donor.save(update_fields=update_fields)

            verified = self._get_article(client, article.article_id)
            if not has_managed_marker(verified.body_html, self.donor):
                raise JoomlaArticleError(
                    f"Материал #{article.article_id} создан и привязан к "
                    "донору, но managed-marker после записи не найден"
                )
            return (
                f"Материал #{article.article_id} создан через JPC Connector "
                "и принят под управление"
            )

    def adopt_article(self, article_id):
        marker = str(self.donor.managed_marker_uuid)
        marker_html = f"<!-- JPC-MANAGED-PAGE:{marker} -->"
        with self._http_client() as client:
            article = self._get_article(client, article_id)
            if marker_html in article.body_html:
                return (
                    f"Материал #{article_id} уже находится под управлением JPC"
                )
            if "<!-- JPC-MANAGED-PAGE:" in article.body_html:
                raise ManagedMarkerMismatch(
                    "Материал содержит marker другого донора JPC"
                )

            snapshot = self._save_snapshot(article, "before_adoption")
            new_html = marker_html + "\n" + article.body_html
            verified, recovered = self._write_and_verify(
                client,
                "adopt",
                article_id,
                new_html,
                marker_uuid=marker,
                expected_hash=sha256(
                    article.body_html.encode()
                ).hexdigest(),
            )
            if not has_managed_marker(verified.body_html, self.donor):
                raise JoomlaArticleError(
                    "JPC Connector не сохранил managed-marker; "
                    "исходный HTML сохранён в snapshot"
                )
            if recovered:
                return (
                    f"Материал #{article_id} принят под управление; "
                    "запись подтверждена после ошибки Connector; "
                    f"backup snapshot #{snapshot.pk}"
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
                    "Публикация запрещена: managed-marker материала "
                    "не совпадает. Сначала выполните принятие под управление."
                )
            if not has_managed_marker(html, self.donor):
                raise ManagedMarkerMismatch(
                    "Публикация запрещена: новый HTML не содержит "
                    "managed-marker текущего донора"
                )

            snapshot = self._save_snapshot(article, "before_update")
            verified, recovered = self._write_and_verify(
                client,
                "update",
                article_id,
                html,
                marker_uuid=str(self.donor.managed_marker_uuid),
                expected_hash=sha256(
                    article.body_html.encode()
                ).hexdigest(),
            )
            if not has_managed_marker(verified.body_html, self.donor):
                raise JoomlaArticleError(
                    "Проверка после записи не пройдена; "
                    f"backup snapshot #{snapshot.pk}"
                )
            if recovered:
                return (
                    f"Материал #{article_id} обновлён; запись подтверждена "
                    "после ошибки Connector; "
                    f"backup snapshot #{snapshot.pk}"
                )
            return (
                f"Материал #{article_id} обновлён через JPC Connector; "
                f"backup snapshot #{snapshot.pk}"
            )
