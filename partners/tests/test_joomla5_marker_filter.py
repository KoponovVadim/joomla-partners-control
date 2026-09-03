import json
import os
import re
from unittest.mock import patch

import httpx
from django.test import TestCase

from partners.joomla.joomla5 import Joomla5Adapter
from partners.models import DonorSite
from partners.services.credentials import encrypt_secret


class FilteredJoomla5Adapter(Joomla5Adapter):
    def __init__(self, donor, state):
        self.state = state
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
                    "fulltext": self.state.get("fulltext", ""),
                },
            }
        }

    @staticmethod
    def _joomla_filter(value):
        return re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)

    def _http_transport(self):
        def handler(request):
            path = request.url.path.rstrip("/")
            collection = path.endswith("/content/articles")

            if request.method == "GET":
                if collection:
                    return httpx.Response(
                        200,
                        json={"data": [self._resource()["data"]]},
                        request=request,
                    )
                return httpx.Response(200, json=self._resource(), request=request)

            if request.method == "PATCH":
                payload = json.loads(request.content.decode())
                self.state["introtext"] = self._joomla_filter(payload["introtext"])
                self.state["fulltext"] = self._joomla_filter(payload["fulltext"])
                return httpx.Response(200, json=self._resource(), request=request)

            return httpx.Response(405, request=request)

        return httpx.MockTransport(handler)


class Joomla5FilteredMarkerTests(TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {"CREDENTIAL_ENCRYPTION_KEY": "joomla5-marker-filter-tests"},
        )
        self.env.start()
        self.addCleanup(self.env.stop)

        self.donor = DonorSite.objects.create(
            name="Joomla 5 filtered donor",
            domain="joomla5-filtered.test",
            admin_url="https://joomla5-filtered.test/administrator/",
            page_url="https://joomla5-filtered.test/partners",
            joomla_version=DonorSite.JoomlaVersion.V5,
            auth_mode=DonorSite.AuthMode.API_TOKEN,
            encrypted_api_token=encrypt_secret("test-api-token"),
            article_id=41,
            article_title="Partners",
            article_category_id=7,
        )
        self.state = {
            "id": 41,
            "title": "Partners",
            "alias": "partners",
            "introtext": "<p>Original</p>",
            "fulltext": "",
        }

    @property
    def canonical_marker(self):
        return f"<!-- JPC-MANAGED-PAGE:{self.donor.managed_marker_uuid} -->"

    @property
    def api_marker(self):
        return (
            f'<span id="jpc-managed-page-{self.donor.managed_marker_uuid}" '
            "hidden></span>"
        )

    def adapter(self):
        return FilteredJoomla5Adapter(self.donor, self.state)

    def test_adoption_survives_joomla_comment_filtering(self):
        message = self.adapter().adopt_article(41)

        self.assertIn("принят под управление", message)
        self.assertTrue(self.state["introtext"].startswith(self.api_marker))
        self.assertNotIn("<!-- JPC-MANAGED-PAGE:", self.state["introtext"])

        article = self.adapter().get_article(41)
        self.assertTrue(article.body_html.startswith(self.canonical_marker))

    def test_update_keeps_filter_safe_marker_and_verifies_canonically(self):
        adapter = self.adapter()
        adapter.adopt_article(41)

        message = adapter.update_article(
            41,
            self.canonical_marker + "\n<p>Updated</p>",
        )

        self.assertIn("обновлён через Joomla 5 API", message)
        self.assertTrue(self.state["introtext"].startswith(self.api_marker))
        self.assertIn("<p>Updated</p>", self.state["introtext"])
        article = adapter.get_article(41)
        self.assertTrue(article.body_html.startswith(self.canonical_marker))
        self.assertIn("<p>Updated</p>", article.body_html)
