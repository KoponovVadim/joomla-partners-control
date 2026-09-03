import json
import os
from unittest.mock import patch

import httpx
from django.test import TestCase

from partners.joomla.exceptions import (
    JoomlaArticleError,
    JoomlaAuthenticationError,
    JoomlaPermissionError,
    ManagedMarkerMismatch,
)
from partners.joomla.joomla4 import Joomla4Adapter
from partners.joomla.joomla5 import Joomla5Adapter
from partners.models import ArticleSnapshot, DonorSite
from partners.services.credentials import encrypt_secret


class MockTransportMixin:
    def __init__(self, donor, state):
        self.state = state
        self.requests = []
        super().__init__(donor)

    def _resource(self):
        return {
            "data": {
                "type": "articles",
                "id": str(self.state["id"]),
                "attributes": {
                    "id": self.state["id"],
                    "title": self.state["title"],
                    "alias": self.state["alias"],
                    "introtext": self.state["introtext"],
                    "fulltext": self.state["fulltext"],
                },
            }
        }

    def _http_transport(self):
        def handler(request):
            self.requests.append(request)
            status = self.state.get("error_status")
            if status:
                return httpx.Response(
                    status,
                    json={"errors": [{"detail": "mock denial"}]},
                    request=request,
                )

            path = request.url.path.rstrip("/")
            collection = path.endswith("/content/articles")
            if request.method == "GET" and collection:
                return httpx.Response(
                    200,
                    json={"data": [self._resource()["data"]]},
                    request=request,
                )
            if request.method == "GET":
                return httpx.Response(200, json=self._resource(), request=request)
            if request.method == "POST" and collection:
                payload = json.loads(request.content.decode())
                self.state["creates"] += 1
                self.state["id"] = self.state.get("new_id", 91)
                self.state["title"] = payload["title"]
                self.state["alias"] = payload["alias"] or "partners-generated"
                self.state["introtext"] = payload["articletext"]
                self.state["fulltext"] = ""
                if self.state.get("drop_marker_after_write"):
                    self.state["introtext"] = "<p>Joomla filtered the marker</p>"
                return httpx.Response(
                    201,
                    json=self._resource(),
                    headers={
                        "Location": (
                            "https://donor.test/api/index.php/v1/content/articles/"
                            f"{self.state['id']}"
                        )
                    },
                    request=request,
                )
            if request.method == "PATCH":
                payload = json.loads(request.content.decode())
                self.state["updates"] += 1
                self.state["introtext"] = payload["introtext"]
                self.state["fulltext"] = payload["fulltext"]
                if self.state.get("drop_marker_after_write"):
                    self.state["introtext"] = "<p>Joomla filtered the marker</p>"
                    self.state["fulltext"] = ""
                return httpx.Response(200, json=self._resource(), request=request)
            return httpx.Response(405, request=request)

        return httpx.MockTransport(handler)


class MockJoomla4Adapter(MockTransportMixin, Joomla4Adapter):
    pass


class MockJoomla5Adapter(MockTransportMixin, Joomla5Adapter):
    pass


class JoomlaApiAdapterTests(TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {"CREDENTIAL_ENCRYPTION_KEY": "joomla-api-tests"},
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.donor = DonorSite.objects.create(
            name="API donor",
            domain="donor.test",
            admin_url="https://donor.test/administrator/",
            page_url="https://donor.test/partners",
            joomla_version=DonorSite.JoomlaVersion.V4,
            auth_mode=DonorSite.AuthMode.API_TOKEN,
            encrypted_api_token=encrypt_secret("test-api-token"),
            article_title="Partners",
            article_category_id=7,
            article_alias="partners",
        )
        self.state = {
            "id": 41,
            "title": "Existing partners",
            "alias": "existing-partners",
            "introtext": "<p>Intro</p>",
            "fulltext": "<p>Full</p>",
            "creates": 0,
            "updates": 0,
        }

    @property
    def marker(self):
        return f"<!-- JPC-MANAGED-PAGE:{self.donor.managed_marker_uuid} -->"

    def adapter(self, cls=MockJoomla4Adapter):
        return cls(self.donor, self.state)

    def test_connection_uses_derived_api_url_and_token_header(self):
        adapter = self.adapter()

        message = adapter.test_connection()

        self.assertIn("Joomla 4 API", message)
        self.assertEqual(
            str(adapter.requests[0].url),
            "https://donor.test/api/index.php/v1/content/articles?page%5Blimit%5D=1",
        )
        self.assertEqual(
            adapter.requests[0].headers["X-Joomla-Token"],
            "test-api-token",
        )
        self.assertEqual(
            adapter.requests[0].headers["Accept"],
            "application/vnd.api+json",
        )

    def test_explicit_api_url_is_used_without_redirect(self):
        self.donor.api_url = "https://api.donor.test/custom/v1/"
        adapter = self.adapter()

        adapter.test_connection()

        self.assertEqual(
            adapter.requests[0].url.host,
            "api.donor.test",
        )
        self.assertEqual(
            adapter.requests[0].url.path,
            "/custom/v1/content/articles",
        )

    def test_get_article_combines_introtext_and_fulltext(self):
        article = self.adapter().get_article(41)

        self.assertEqual(article.article_id, 41)
        self.assertEqual(
            article.body_html,
            '<p>Intro</p><hr id="system-readmore" /><p>Full</p>',
        )

    def test_create_persists_id_and_alias_before_marker_verification(self):
        self.donor.article_id = None
        self.state["new_id"] = 91
        self.state["drop_marker_after_write"] = True
        adapter = self.adapter()

        with self.assertRaisesRegex(
            JoomlaArticleError,
            "создан и привязан",
        ):
            adapter.create_article(
                html=self.marker + "\n<ul></ul>",
                title="Partners",
                alias="",
                category_id=7,
            )

        self.donor.refresh_from_db()
        self.assertEqual(self.donor.article_id, 91)
        self.assertEqual(self.donor.article_alias, "partners-generated")
        self.assertEqual(self.state["creates"], 1)

        with self.assertRaises(ManagedMarkerMismatch):
            adapter.update_article(
                self.donor.article_id,
                self.marker + "\n<ul><li>Retry</li></ul>",
            )
        self.assertEqual(self.state["creates"], 1)

    def test_create_sends_official_article_payload_and_verifies_marker(self):
        self.donor.article_id = None
        adapter = self.adapter()

        message = adapter.create_article(
            html=self.marker + "\n<ul></ul>",
            title="Partners",
            alias="partners",
            category_id=7,
        )

        post = next(request for request in adapter.requests if request.method == "POST")
        payload = json.loads(post.content.decode())
        self.assertEqual(payload["articletext"], self.marker + "\n<ul></ul>")
        self.assertEqual(payload["catid"], 7)
        self.assertEqual(payload["language"], "*")
        self.assertIn("создан через Joomla 4 API", message)
        self.assertEqual(self.state["creates"], 1)

    def test_update_splits_readmore_and_creates_snapshot(self):
        self.donor.article_id = 41
        self.donor.save(update_fields=["article_id"])
        self.state["introtext"] = self.marker + "\n<p>Old intro</p>"
        self.state["fulltext"] = "<p>Old full</p>"
        new_html = (
            self.marker
            + "\n<p>New intro</p>"
            + '<hr id="system-readmore" />'
            + "<p>New full</p>"
        )

        message = self.adapter().update_article(41, new_html)

        self.assertEqual(
            self.state["introtext"],
            self.marker + "\n<p>New intro</p>",
        )
        self.assertEqual(self.state["fulltext"], "<p>New full</p>")
        snapshot = ArticleSnapshot.objects.get()
        self.assertEqual(snapshot.reason, "before_update")
        self.assertIn("Old intro", snapshot.body_html)
        self.assertIn("backup snapshot", message)

    def test_unmanaged_article_is_never_overwritten(self):
        self.donor.article_id = 41
        self.donor.save(update_fields=["article_id"])

        with self.assertRaises(ManagedMarkerMismatch):
            self.adapter().update_article(41, self.marker + "\n<p>New</p>")

        self.assertEqual(self.state["updates"], 0)
        self.assertFalse(ArticleSnapshot.objects.exists())

    def test_adoption_saves_original_and_adds_marker(self):
        self.donor.article_id = 41
        self.donor.save(update_fields=["article_id"])

        message = self.adapter().adopt_article(41)

        snapshot = ArticleSnapshot.objects.get()
        self.assertEqual(snapshot.reason, "before_adoption")
        self.assertEqual(snapshot.body_html, '<p>Intro</p><hr id="system-readmore" /><p>Full</p>')
        self.assertTrue(self.state["introtext"].startswith(self.marker))
        self.assertIn("принят под управление", message)

    def test_authentication_and_permission_errors_are_specific(self):
        cases = (
            (401, JoomlaAuthenticationError, "X-Joomla-Token"),
            (403, JoomlaPermissionError, "core.login.api"),
        )
        for status, exception, message in cases:
            with self.subTest(status=status):
                self.state["error_status"] = status
                with self.assertRaisesRegex(exception, message):
                    self.adapter().test_connection()
        self.assertNotIn(
            "test-api-token",
            "\n".join(str(request.url) for request in self.adapter().requests),
        )

    def test_joomla5_uses_same_web_services_contract(self):
        self.donor.joomla_version = DonorSite.JoomlaVersion.V5

        message = self.adapter(MockJoomla5Adapter).test_connection()

        self.assertIn("Joomla 5 API", message)
