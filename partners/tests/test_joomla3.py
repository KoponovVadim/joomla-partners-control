import os
from urllib.parse import parse_qs

import httpx
from django.test import TestCase

from partners.joomla.exceptions import JoomlaPermissionError, ManagedMarkerMismatch
from partners.joomla.joomla3 import Joomla3Adapter
from partners.models import ArticleSnapshot, DonorSite
from partners.services.credentials import encrypt_password


LOGIN = '''<form id="form-login" action="/administrator/index.php" method="post">
<input name="username"><input name="passwd"><input name="option" value="com_login">
<input name="task" value="login"><input name="return" value="abc"><input name="token123" value="1">
</form>'''


def article_form(article_id, html, title="Partners", alias="partners", category_id=2):
    return f'''<form id="item-form" action="/administrator/index.php?option=com_content&id={article_id}">
    <input name="jform[id]" value="{article_id}"><input name="jform[title]" value="{title}">
    <input name="jform[alias]" value="{alias}"><select name="jform[catid]"><option selected value="{category_id}">Cat</option></select>
    <input name="jform[state]" value="1"><textarea name="jform[articletext]">{html}</textarea>
    <input name="task" value=""><input name="csrf123" value="1"></form>'''


def article_list_form(message=""):
    return f'''{message}<form id="adminForm" action="/administrator/index.php?option=com_content&view=articles" method="post">
    <input name="task" value=""><input name="filter_search" value=""><input name="csrf_list" value="1">
    </form>'''


class MockJoomla3Adapter(Joomla3Adapter):
    def __init__(self, donor, state):
        super().__init__(donor)
        self.state = state

    def _http_client(self):
        state = self.state

        def handler(request):
            query = str(request.url)
            if request.method == "GET" and "task=article.edit" in query:
                if state.get("locked"):
                    return httpx.Response(
                        200,
                        text='<div id="system-message-container"><div class="alert alert-error">Checked out by another user</div></div>',
                        request=request,
                    )
                html = article_form(
                    87,
                    state["html"],
                    title=state.get("title", "Partners"),
                    alias=state.get("alias", "partners"),
                    category_id=state.get("category_id", 2),
                )
                return httpx.Response(200, text=html, request=request)
            if request.method == "GET" and "task=article.add" in query:
                return httpx.Response(
                    200,
                    text=article_form(0, "", title="", alias="", category_id=2),
                    request=request,
                )
            if request.method == "GET" and "view=articles" in query:
                return httpx.Response(200, text=article_list_form(), request=request)
            if request.method == "GET":
                return httpx.Response(200, text=LOGIN, request=request)

            data = parse_qs(request.content.decode(), keep_blank_values=True)
            if data.get("task") == ["login"]:
                return httpx.Response(200, text='<div id="menu">Admin</div>', request=request)
            if data.get("task") == ["articles.checkin"]:
                state["checkins"] += 1
                if state.get("checkin_denied"):
                    return httpx.Response(
                        200,
                        text=article_list_form('<div class="alert alert-error">Check-in not permitted</div>'),
                        request=request,
                    )
                state["locked"] = False
                return httpx.Response(200, text=article_list_form(), request=request)
            if data.get("task") == ["article.save"]:
                state["html"] = data["jform[articletext]"][0]
                state["saves"] += 1
            if data.get("task") == ["article.apply"]:
                state["html"] = data["jform[articletext]"][0]
                state["title"] = data["jform[title]"][0]
                state["alias"] = data["jform[alias]"][0] or "partners-generated"
                state["category_id"] = int(data["jform[catid]"][0])
                state["saves"] += 1
                new_id = state.get("new_id", 91)
                html = article_form(
                    new_id,
                    state["html"],
                    title=state["title"],
                    alias=state["alias"],
                    category_id=state["category_id"],
                )
                return httpx.Response(200, text=html, request=request)
            if data.get("task") == ["article.cancel"]:
                state["cancels"] += 1
            return httpx.Response(200, text='<div id="menu">Admin</div>', request=request)

        return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


class Joomla3AdapterTests(TestCase):
    def setUp(self):
        os.environ["CREDENTIAL_ENCRYPTION_KEY"] = "joomla-adapter-test-key"
        self.donor = DonorSite.objects.create(
            name="D",
            domain="d.test",
            admin_url="https://d.test/administrator/",
            page_url="https://d.test/partners",
            joomla_version="3",
            username="dm-control",
            encrypted_password=encrypt_password("secret"),
            article_id=87,
        )
        self.state = {
            "html": "<p>Existing article</p>",
            "saves": 0,
            "cancels": 0,
            "checkins": 0,
            "locked": False,
        }
        self.adapter = MockJoomla3Adapter(self.donor, self.state)

    def test_connection_reads_article_and_releases_edit_lock(self):
        message = self.adapter.test_connection()
        self.assertIn("материал #87 доступен", message)
        self.assertEqual(self.state["cancels"], 1)
        self.assertEqual(self.state["checkins"], 0)
        self.assertEqual(self.state["saves"], 0)

    def test_create_article_saves_id_alias_category_and_managed_marker(self):
        self.donor.article_id = None
        self.donor.article_title = "Наши партнёры"
        self.donor.article_alias = ""
        self.donor.article_category_id = 7
        self.donor.save(
            update_fields=["article_id", "article_title", "article_alias", "article_category_id", "updated_at"]
        )
        marker = f"<!-- JPC-MANAGED-PAGE:{self.donor.managed_marker_uuid} -->"
        message = self.adapter.create_article(html=marker + "\n<ul></ul>")

        self.donor.refresh_from_db()
        self.assertIn("Материал #91 создан", message)
        self.assertEqual(self.donor.article_id, 91)
        self.assertEqual(self.donor.article_alias, "partners-generated")
        self.assertEqual(self.state["title"], "Наши партнёры")
        self.assertEqual(self.state["category_id"], 7)
        self.assertIn(marker, self.state["html"])
        self.assertEqual(self.state["saves"], 1)
        self.assertEqual(self.state["cancels"], 1)

    def test_adopt_backs_up_then_update_requires_marker(self):
        message = self.adapter.adopt_article(87)
        self.assertIn("принят под управление", message)
        snapshot = ArticleSnapshot.objects.get()
        self.assertEqual(snapshot.body_html, "<p>Existing article</p>")
        self.assertIn(str(self.donor.managed_marker_uuid), self.state["html"])
        self.adapter.update_article(
            87,
            f"<!-- JPC-MANAGED-PAGE:{self.donor.managed_marker_uuid} -->\n<ul></ul>",
        )
        self.assertIn("<ul></ul>", self.state["html"])
        self.assertEqual(ArticleSnapshot.objects.count(), 2)
        self.assertGreaterEqual(self.state["checkins"], 2)

    def test_update_without_marker_is_blocked(self):
        with self.assertRaises(ManagedMarkerMismatch):
            self.adapter.update_article(87, "replacement")
        self.assertEqual(self.state["saves"], 0)
        self.assertEqual(ArticleSnapshot.objects.count(), 0)

    def test_locked_managed_article_is_checked_in_automatically_before_update(self):
        marker = f"<!-- JPC-MANAGED-PAGE:{self.donor.managed_marker_uuid} -->"
        self.state["html"] = marker + "\n<ul><li>old</li></ul>"
        self.state["locked"] = True

        message = self.adapter.update_article(87, marker + "\n<ul><li>new</li></ul>")

        self.assertIn("Материал #87 обновлён", message)
        self.assertFalse(self.state["locked"])
        self.assertGreaterEqual(self.state["checkins"], 1)
        self.assertIn("<li>new</li>", self.state["html"])
        self.assertEqual(ArticleSnapshot.objects.count(), 1)

    def test_locked_article_reports_missing_checkin_permission(self):
        marker = f"<!-- JPC-MANAGED-PAGE:{self.donor.managed_marker_uuid} -->"
        self.state["html"] = marker + "\n<ul></ul>"
        self.state["locked"] = True
        self.state["checkin_denied"] = True

        with self.assertRaises(JoomlaPermissionError) as caught:
            self.adapter.update_article(87, marker + "\n<ul><li>new</li></ul>")

        self.assertIn("core.manage", str(caught.exception))
        self.assertEqual(self.state["saves"], 0)
        self.assertEqual(ArticleSnapshot.objects.count(), 0)
