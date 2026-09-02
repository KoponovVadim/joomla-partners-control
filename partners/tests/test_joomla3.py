import os
from urllib.parse import parse_qs

import httpx
from django.test import TestCase

from partners.joomla.exceptions import ManagedMarkerMismatch
from partners.joomla.joomla3 import Joomla3Adapter
from partners.models import ArticleSnapshot, DonorSite
from partners.services.credentials import encrypt_password


LOGIN = '''<form id="form-login" action="/administrator/index.php" method="post">
<input name="username"><input name="passwd"><input name="option" value="com_login">
<input name="task" value="login"><input name="return" value="abc"><input name="token123" value="1">
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
                html = f'''<form id="item-form" action="/administrator/index.php?option=com_content&id=87">
                <input name="jform[id]" value="87"><input name="jform[title]" value="Partners">
                <input name="jform[alias]" value="partners"><select name="jform[catid]"><option selected value="2">Cat</option></select>
                <textarea name="jform[articletext]">{state["html"]}</textarea>
                <input name="task" value=""><input name="csrf123" value="1"></form>'''
                return httpx.Response(200, text=html, request=request)
            if request.method == "GET":
                return httpx.Response(200, text=LOGIN, request=request)
            data = parse_qs(request.content.decode(), keep_blank_values=True)
            if data.get("task") == ["login"]:
                return httpx.Response(200, text='<div id="menu">Admin</div>', request=request)
            if data.get("task") == ["article.save"]:
                state["html"] = data["jform[articletext]"][0]
                state["saves"] += 1
            if data.get("task") == ["article.cancel"]:
                state["cancels"] += 1
            return httpx.Response(200, text='<div id="menu">Admin</div>', request=request)

        return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


class Joomla3AdapterTests(TestCase):
    def setUp(self):
        os.environ["CREDENTIAL_ENCRYPTION_KEY"] = "joomla-adapter-test-key"
        self.donor = DonorSite.objects.create(
            name="D", domain="d.test", admin_url="https://d.test/administrator/",
            page_url="https://d.test/partners", joomla_version="3", username="dm-control",
            encrypted_password=encrypt_password("secret"), article_id=87,
        )
        self.state = {"html": "<p>Existing article</p>", "saves": 0, "cancels": 0}
        self.adapter = MockJoomla3Adapter(self.donor, self.state)

    def test_connection_reads_article_and_releases_edit_lock(self):
        message = self.adapter.test_connection()
        self.assertIn("материал #87 доступен", message)
        self.assertEqual(self.state["cancels"], 1)
        self.assertEqual(self.state["saves"], 0)

    def test_adopt_backs_up_then_update_requires_marker(self):
        message = self.adapter.adopt_article(87)
        self.assertIn("принят под управление", message)
        snapshot = ArticleSnapshot.objects.get()
        self.assertEqual(snapshot.body_html, "<p>Existing article</p>")
        self.assertIn(str(self.donor.managed_marker_uuid), self.state["html"])
        self.adapter.update_article(87, f"<!-- JPC-MANAGED-PAGE:{self.donor.managed_marker_uuid} -->\n<ul></ul>")
        self.assertIn("<ul></ul>", self.state["html"])
        self.assertEqual(ArticleSnapshot.objects.count(), 2)

    def test_update_without_marker_is_blocked(self):
        with self.assertRaises(ManagedMarkerMismatch):
            self.adapter.update_article(87, "replacement")
        self.assertEqual(self.state["saves"], 0)
        self.assertEqual(ArticleSnapshot.objects.count(), 0)
