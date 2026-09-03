from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

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
class JoomlaArticle:
    article_id: int
    title: str
    alias: str
    body_html: str


class Joomla3Adapter(JoomlaAdapter):
    version = "3"
    user_agent = "JoomlaPartnersControl/1.0"

    def _http_client(self):
        return httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=10.0),
            headers={"User-Agent": self.user_agent},
        )

    @property
    def admin_url(self):
        return self.donor.admin_url.rstrip("/") + "/"

    @staticmethod
    def _form_values(form):
        values = []
        for field in form.select("input[name], textarea[name], select[name]"):
            name = field.get("name")
            if field.name == "input":
                field_type = field.get("type", "text").lower()
                if field_type in {"submit", "button", "file", "image", "reset"}:
                    continue
                if field_type in {"checkbox", "radio"} and not field.has_attr("checked"):
                    continue
                values.append((name, field.get("value", "")))
            elif field.name == "textarea":
                values.append((name, field.decode_contents(formatter=None)))
            else:
                selected = field.select("option[selected]") or field.select("option:not([disabled])")[:1]
                values.extend((name, option.get("value", option.text)) for option in selected)
        return values

    @staticmethod
    def _replace(values, name, value):
        return [(key, old) for key, old in values if key != name] + [(name, str(value))]

    @staticmethod
    def _article_id_from_response(response, form=None):
        if form is not None:
            field = form.select_one('[name="jform[id]"]')
            if field and str(field.get("value", "")).isdigit():
                return int(field["value"])
        query = parse_qs(urlparse(str(response.url)).query)
        values = query.get("id", [])
        if values and str(values[0]).isdigit():
            return int(values[0])
        return None

    @staticmethod
    def _raise_form_error(soup, prefix="Joomla отклонила сохранение"):
        error = soup.select_one(".alert-error, .alert-danger")
        if error:
            raise JoomlaArticleError(f"{prefix}: " + " ".join(error.stripped_strings)[:300])

    def _request(self, client, method, url, **kwargs):
        try:
            response = client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except (httpx.HTTPError, OSError) as exc:
            raise JoomlaConnectionError(f"Ошибка HTTP при обращении к Joomla: {exc}") from exc

    def _post_form(self, client, url, values):
        return self._request(
            client,
            "POST",
            url,
            content=str(httpx.QueryParams(values)).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    def _login(self, client):
        username, password = self.credentials()
        if not username or not password:
            raise JoomlaAuthenticationError("Не заполнены логин или пароль Joomla")
        response = self._request(client, "GET", self.admin_url)
        soup = BeautifulSoup(response.text, "html.parser")
        form = soup.select_one("form#form-login")
        if not form:
            if soup.select_one("a[href*='task=logout'], .nav-user, #menu"):
                return
            raise JoomlaAuthenticationError("Joomla не вернула ожидаемую форму входа")
        values = self._form_values(form)
        values = self._replace(values, "username", username)
        values = self._replace(values, "passwd", password)
        action = urljoin(str(response.url), form.get("action") or "index.php")
        response = self._post_form(client, action, values)
        result = BeautifulSoup(response.text, "html.parser")
        if result.select_one("form#form-login"):
            alert = result.select_one(".alert-error, .alert-danger, #system-message-container")
            detail = " ".join(alert.stripped_strings) if alert else "неверный логин, пароль или недостаточно прав"
            raise JoomlaAuthenticationError(f"Вход в Joomla не выполнен: {detail[:300]}")

    def _load_article_form(self, client, article_id):
        url = urljoin(
            self.admin_url,
            f"index.php?option=com_content&task=article.edit&id={int(article_id)}",
        )
        response = self._request(client, "GET", url)
        soup = BeautifulSoup(response.text, "html.parser")
        if soup.select_one("form#form-login"):
            raise JoomlaAuthenticationError("Сессия Joomla завершилась")
        form = soup.select_one("form#item-form")
        if not form:
            alert = soup.select_one(".alert-error, .alert-danger, #system-message-container")
            detail = " ".join(alert.stripped_strings) if alert else "форма редактирования недоступна"
            raise JoomlaPermissionError(f"Материал #{article_id}: {detail[:300]}")
        editor = form.select_one('[name="jform[articletext]"]')
        if not editor:
            raise JoomlaArticleError("Редактор Joomla не содержит поле jform[articletext]")
        title = form.select_one('[name="jform[title]"]')
        alias = form.select_one('[name="jform[alias]"]')
        article = JoomlaArticle(
            int(article_id),
            title.get("value", "") if title else "",
            alias.get("value", "") if alias else "",
            editor.decode_contents(formatter=None),
        )
        return response, form, article

    def _load_article_list_form(self, client):
        url = urljoin(self.admin_url, "index.php?option=com_content&view=articles")
        response = self._request(client, "GET", url)
        soup = BeautifulSoup(response.text, "html.parser")
        if soup.select_one("form#form-login"):
            raise JoomlaAuthenticationError("Сессия Joomla завершилась")
        form = soup.select_one("form#adminForm")
        if not form:
            alert = soup.select_one(".alert-error, .alert-danger, #system-message-container")
            detail = " ".join(alert.stripped_strings) if alert else "список материалов недоступен"
            raise JoomlaPermissionError(f"Joomla не вернула список материалов: {detail[:300]}")
        return response, form

    def _force_checkin_article(self, client, article_id):
        response, form = self._load_article_list_form(client)
        values = self._form_values(form)
        values = self._replace(values, "task", "articles.checkin")
        values = self._replace(values, "cid[]", int(article_id))
        action = urljoin(
            str(response.url),
            form.get("action") or "index.php?option=com_content&view=articles",
        )
        checked = self._post_form(client, action, values)
        result = BeautifulSoup(checked.text, "html.parser")
        if result.select_one("form#form-login"):
            raise JoomlaAuthenticationError("Сессия Joomla завершилась во время Check-in")
        error = result.select_one(".alert-error, .alert-danger")
        if error:
            detail = " ".join(error.stripped_strings)[:300]
            raise JoomlaPermissionError(
                f"Не удалось снять блокировку материала #{article_id}: {detail}. "
                "Сервисному пользователю Joomla требуется право Check-in (core.manage для com_checkin)."
            )
        return checked

    def _load_article_form_for_write(self, client, article_id):
        self._force_checkin_article(client, article_id)
        try:
            return self._load_article_form(client, article_id)
        except JoomlaPermissionError as exc:
            raise JoomlaPermissionError(
                f"Материал #{article_id} недоступен после автоматического Check-in. "
                "Проверьте, что сервисный пользователь Joomla имеет право Check-in "
                "(core.manage для com_checkin) и право редактирования материала."
            ) from exc

    def _load_new_article_form(self, client):
        url = urljoin(self.admin_url, "index.php?option=com_content&task=article.add")
        response = self._request(client, "GET", url)
        soup = BeautifulSoup(response.text, "html.parser")
        if soup.select_one("form#form-login"):
            raise JoomlaAuthenticationError("Сессия Joomla завершилась")
        form = soup.select_one("form#item-form")
        if not form:
            alert = soup.select_one(".alert-error, .alert-danger, #system-message-container")
            detail = " ".join(alert.stripped_strings) if alert else "форма создания материала недоступна"
            raise JoomlaPermissionError(f"Создание материала недоступно: {detail[:300]}")
        if not form.select_one('[name="jform[articletext]"]'):
            raise JoomlaArticleError("Форма создания Joomla не содержит поле jform[articletext]")
        return response, form

    def _save_snapshot(self, article, reason):
        return ArticleSnapshot.objects.create(
            donor=self.donor,
            article_id=article.article_id,
            title=article.title,
            body_html=article.body_html,
            body_hash=sha256(article.body_html.encode()).hexdigest(),
            reason=reason,
        )

    def _submit_article(self, client, response, form, html):
        values = self._form_values(form)
        values = self._replace(values, "jform[articletext]", html)
        values = self._replace(values, "task", "article.save")
        action = urljoin(str(response.url), form.get("action") or "index.php")
        saved = self._post_form(client, action, values)
        self._raise_form_error(BeautifulSoup(saved.text, "html.parser"))
        return saved

    def _cancel_article(self, client, response, form):
        values = self._replace(self._form_values(form), "task", "article.cancel")
        action = urljoin(str(response.url), form.get("action") or "index.php")
        self._post_form(client, action, values)

    def test_connection(self):
        with self._http_client() as client:
            self._login(client)
            if self.donor.article_id:
                response, form, article = self._load_article_form(client, self.donor.article_id)
                self._cancel_article(client, response, form)
                return f"Joomla 3: вход выполнен, материал #{article.article_id} доступен — {article.title}"
            return "Joomla 3: вход в administrator выполнен"

    def get_article(self, article_id):
        with self._http_client() as client:
            self._login(client)
            response, form, article = self._load_article_form(client, article_id)
            self._cancel_article(client, response, form)
            return article

    def create_article(self, alias="", html="", title=None, category_id=None, **kwargs):
        title = (title or self.donor.article_title or "Наши партнёры").strip()
        category_id = category_id or self.donor.article_category_id or 2
        alias = alias or self.donor.article_alias
        if not title:
            raise JoomlaArticleError("Для создания материала не задан заголовок")

        with self._http_client() as client:
            self._login(client)
            response, form = self._load_new_article_form(client)
            values = self._form_values(form)
            values = self._replace(values, "jform[title]", title)
            values = self._replace(values, "jform[alias]", alias)
            values = self._replace(values, "jform[catid]", category_id)
            values = self._replace(values, "jform[articletext]", html)
            values = self._replace(values, "jform[state]", 1)
            values = self._replace(values, "task", "article.apply")
            action = urljoin(str(response.url), form.get("action") or "index.php")
            saved = self._post_form(client, action, values)
            result = BeautifulSoup(saved.text, "html.parser")
            self._raise_form_error(result, "Joomla отклонила создание материала")

            saved_form = result.select_one("form#item-form")
            article_id = self._article_id_from_response(saved, saved_form)
            if not article_id:
                raise JoomlaArticleError(
                    "Joomla сохранила форму без определяемого ID материала; автоматическая привязка остановлена"
                )

            saved_alias = alias
            if saved_form:
                alias_field = saved_form.select_one('[name="jform[alias]"]')
                saved_alias = alias_field.get("value", "") if alias_field else alias

            # Persist the Joomla identity before any post-create verification.
            # The article already exists at this point, so losing its ID would
            # make a retry create a duplicate instead of updating it.
            self.donor.article_id = article_id
            update_fields = ["article_id", "updated_at"]
            if saved_alias and saved_alias != self.donor.article_alias:
                self.donor.article_alias = saved_alias
                update_fields.append("article_alias")
            self.donor.save(update_fields=update_fields)

            if not saved_form:
                raise JoomlaArticleError(
                    f"Материал создан как #{article_id} и привязан к донору, но Joomla не вернула форму для проверки"
                )

            editor = saved_form.select_one('[name="jform[articletext]"]')
            saved_html = editor.decode_contents(formatter=None) if editor else ""
            self._cancel_article(client, saved, saved_form)

            if not has_managed_marker(saved_html, self.donor):
                raise JoomlaArticleError(
                    f"Материал #{article_id} создан и привязан к донору, но managed-marker после записи не найден; дальнейшая синхронизация остановлена"
                )

            return f"Материал #{article_id} создан и принят под управление JPC"

    def adopt_article(self, article_id):
        with self._http_client() as client:
            self._login(client)
            response, form, article = self._load_article_form_for_write(client, article_id)
            expected = f"<!-- JPC-MANAGED-PAGE:{self.donor.managed_marker_uuid} -->"
            if expected in article.body_html:
                self._cancel_article(client, response, form)
                return f"Материал #{article_id} уже находится под управлением JPC"
            if "<!-- JPC-MANAGED-PAGE:" in article.body_html:
                self._cancel_article(client, response, form)
                raise ManagedMarkerMismatch("Материал содержит marker другого донора JPC")
            snapshot = self._save_snapshot(article, "before_adoption")
            self._submit_article(client, response, form, expected + "\n" + article.body_html)
            verify_response, verify_form, verified = self._load_article_form_for_write(client, article_id)
            self._cancel_article(client, verify_response, verify_form)
            if not has_managed_marker(verified.body_html, self.donor):
                raise JoomlaArticleError(
                    "Joomla не сохранила managed-marker; исходный HTML сохранён в snapshot"
                )
            return f"Материал #{article_id} принят под управление; backup snapshot #{snapshot.pk}"

    def update_article(self, article_id, html):
        with self._http_client() as client:
            self._login(client)
            response, form, article = self._load_article_form_for_write(client, article_id)
            if not has_managed_marker(article.body_html, self.donor):
                self._cancel_article(client, response, form)
                raise ManagedMarkerMismatch(
                    "Публикация запрещена: managed-marker материала не совпадает. Сначала выполните принятие под управление."
                )
            snapshot = self._save_snapshot(article, "before_update")
            self._submit_article(client, response, form, html)
            verify_response, verify_form, verified = self._load_article_form_for_write(client, article_id)
            self._cancel_article(client, verify_response, verify_form)
            if not has_managed_marker(verified.body_html, self.donor):
                raise JoomlaArticleError(
                    f"Проверка после записи не пройдена; backup snapshot #{snapshot.pk}"
                )
            return f"Материал #{article_id} обновлён; backup snapshot #{snapshot.pk}"
