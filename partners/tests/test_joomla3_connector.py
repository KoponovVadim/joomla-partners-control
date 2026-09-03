import json
import os
from hashlib import sha256
from unittest.mock import patch

import httpx
from django.test import TestCase

from partners.joomla import get_adapter
from partners.joomla.exceptions import (
    JoomlaArticleError,
    JoomlaAuthenticationError,
    ManagedMarkerMismatch,
)
from partners.joomla.joomla3_connector import Joomla3ConnectorAdapter
from partners.models import ArticleSnapshot, DonorSite
from partners.services.credentials import encrypt_secret


class MockConnectorAdapter(Joomla3ConnectorAdapter):
    def __init__(self, donor, state):
        self.state = state
        self.requests = []
        super().__init__(donor)

    def _http_transport(self):
        def handler(request):
            self.requests.append(request)
            payload = json.loads(request.content.decode())
            action = payload["action"]

            if self.state.get("status"):
                return httpx.Response(
                    self.state["status"],
                    json={
                        "ok": False,
                        "error": self.state.get(
                            "error",
                            "connector error",
                        ),
                    },
                    request=request,
                )

            if action == "ping":
                data = {
                    "connector_version": "1.0.0",
                    "joomla_version": "3.10.12",
                }
            elif action == "get":
                data = self._state_article()
            elif action == "create":
                self.state["creates"] += 1
                self.state["id"] = self.state.get("new_id", 91)
                self.state["title"] = payload["title"]
                self.state["alias"] = (
                    self.state.get("response_alias")
                    or payload["alias"]
                    or "partners-generated"
                )
                self.state["html"] = payload["html"]
                if self.state.get("drop_marker_after_create"):
                    self.state["html"] = "<p>marker filtered</p>"
                data = self._state_article()
            elif action in {"adopt", "update"}:
                expected = sha256(
                    self.state["html"].encode()
                ).hexdigest()
                if payload["expected_hash"] != expected:
                    return httpx.Response(
                        409,
                        json={
                            "ok": False,
                            "error": "article changed",
                        },
                        request=request,
                    )
                self.state["updates"] += 1
                self.state["html"] = payload["html"]
                data = self._state_article()
            else:
                return httpx.Response(400, request=request)

            return httpx.Response(
                200,
                json={"ok": True, "data": data},
                request=request,
            )

        return httpx.MockTransport(handler)

    def _state_article(self):
        return {
            "id": self.state["id"],
            "title": self.state["title"],
            "alias": self.state["alias"],
            "body_html": self.state["html"],
        }


class Joomla3ConnectorAdapterTests(TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {"CREDENTIAL_ENCRYPTION_KEY": "connector-adapter-tests"},
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.token = "a1" * 32
        self.donor = DonorSite.objects.create(
            name="Connector donor",
            domain="connector.test",
            admin_url="https://connector.test/administrator/",
            page_url="https://connector.test/partners",
            joomla_version=DonorSite.JoomlaVersion.V3,
            auth_mode=DonorSite.AuthMode.CONNECTOR_TOKEN,
            encrypted_connector_token=encrypt_secret(self.token),
            article_id=46,
            article_title="Partners",
            article_category_id=2,
        )
        self.marker = (
            f"<!-- JPC-MANAGED-PAGE:"
            f"{self.donor.managed_marker_uuid} -->"
        )
        self.state = {
            "id": 46,
            "title": "Partners",
            "alias": "partners",
            "html": self.marker + "\n<ul><li>Old</li></ul>",
            "creates": 0,
            "updates": 0,
        }

    def adapter(self):
        return MockConnectorAdapter(self.donor, self.state)

    def test_get_adapter_selects_connector_for_joomla3(self):
        adapter = get_adapter(self.donor)

        self.assertIsInstance(adapter, Joomla3ConnectorAdapter)

    def test_connection_uses_public_endpoint_and_token_header(self):
        adapter = self.adapter()

        message = adapter.test_connection()

        self.assertIn("JPC Connector 1.0.0", message)
        self.assertIn("материал #46 доступен", message)
        self.assertEqual(
            str(adapter.requests[0].url),
            (
                "https://connector.test/index.php"
                "?option=com_ajax&plugin=jpcconnector&format=raw"
            ),
        )
        self.assertEqual(
            adapter.requests[0].headers["X-JPC-Token"],
            self.token,
        )
        self.assertNotIn("/administrator/", str(adapter.requests[0].url))

    def test_update_creates_snapshot_and_uses_optimistic_hash(self):
        old_html = self.state["html"]
        new_html = self.marker + "\n<ul><li>New</li></ul>"
        adapter = self.adapter()

        message = adapter.update_article(46, new_html)

        self.assertEqual(self.state["html"], new_html)
        self.assertEqual(self.state["updates"], 1)
        snapshot = ArticleSnapshot.objects.get()
        self.assertEqual(snapshot.reason, "before_update")
        self.assertEqual(snapshot.body_html, old_html)
        update_request = adapter.requests[-2]
        payload = json.loads(update_request.content.decode())
        self.assertEqual(
            payload["expected_hash"],
            sha256(old_html.encode()).hexdigest(),
        )
        self.assertIn("обновлён через JPC Connector", message)

    def test_update_never_overwrites_unmanaged_article(self):
        self.state["html"] = "<p>Unmanaged</p>"

        with self.assertRaises(ManagedMarkerMismatch):
            self.adapter().update_article(
                46,
                self.marker + "\n<p>Replacement</p>",
            )

        self.assertEqual(self.state["updates"], 0)
        self.assertFalse(ArticleSnapshot.objects.exists())

    def test_adoption_backs_up_original_and_adds_marker(self):
        self.state["html"] = "<p>Original unmanaged article</p>"

        message = self.adapter().adopt_article(46)

        self.assertTrue(self.state["html"].startswith(self.marker))
        snapshot = ArticleSnapshot.objects.get()
        self.assertEqual(snapshot.reason, "before_adoption")
        self.assertEqual(
            snapshot.body_html,
            "<p>Original unmanaged article</p>",
        )
        self.assertIn("принят под управление", message)

    def test_create_persists_identity_before_marker_verification(self):
        self.donor.article_id = None
        self.donor.article_alias = ""
        self.donor.save(
            update_fields=["article_id", "article_alias", "updated_at"]
        )
        self.state["new_id"] = 92
        self.state["response_alias"] = "partners-generated"
        self.state["drop_marker_after_create"] = True
        adapter = self.adapter()

        with self.assertRaisesRegex(
            JoomlaArticleError,
            "создан и привязан",
        ):
            adapter.create_article(
                html=self.marker + "\n<ul></ul>",
                title="Partners",
                category_id=2,
            )

        self.donor.refresh_from_db()
        self.assertEqual(self.donor.article_id, 92)
        self.assertEqual(
            self.donor.article_alias,
            "partners-generated",
        )
        self.assertEqual(self.state["creates"], 1)

    def test_create_requires_current_donor_marker(self):
        self.donor.article_id = None

        with self.assertRaises(ManagedMarkerMismatch):
            self.adapter().create_article(
                html="<ul></ul>",
                title="Partners",
                category_id=2,
            )

        self.assertEqual(self.state["creates"], 0)

    def test_connector_conflict_is_reported_without_token(self):
        self.state["status"] = 409
        self.state["error"] = f"changed; token={self.token}"

        with self.assertRaises(JoomlaArticleError) as caught:
            self.adapter().get_article(46)

        message = str(caught.exception)
        self.assertIn("конфликт", message)
        self.assertIn("[REDACTED]", message)
        self.assertNotIn(self.token, message)

    def test_short_token_is_rejected_before_request(self):
        self.donor.encrypted_connector_token = encrypt_secret("short")

        with self.assertRaises(JoomlaAuthenticationError):
            self.adapter().test_connection()
