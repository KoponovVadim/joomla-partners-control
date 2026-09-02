import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from partners.models import ClientSite, DonorSite, PageTemplate, Placement


class PlacementViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("operator", password="test")
        self.client.force_login(self.user)
        self.donor = DonorSite.objects.create(
            name="D",
            domain="d.test",
            admin_url="https://d.test/admin",
            page_url="https://d.test/p",
        )
        self.clients = [ClientSite.objects.create(name=f"C{i}", domain=f"c{i}.test") for i in range(3)]
        self.placements = [
            Placement.objects.create(donor=self.donor, client=client, position=index + 1)
            for index, client in enumerate(self.clients)
        ]

    def test_reorder_and_toggle(self):
        ids = [placement.pk for placement in reversed(self.placements)]
        response = self.client.post(
            reverse("placements-reorder"),
            json.dumps({"ids": ids}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(self.donor.placements.values_list("pk", flat=True)), ids)
        self.assertEqual(
            list(self.donor.placements.values_list("position", flat=True)),
            [1, 2, 3],
        )

        response = self.client.post(reverse("placement-toggle", args=[ids[0]]))
        self.assertFalse(response.json()["enabled"])

    def test_reorder_rejects_placements_from_different_donors(self):
        other_donor = DonorSite.objects.create(
            name="Other",
            domain="other.test",
            admin_url="https://other.test/admin",
            page_url="https://other.test/p",
        )
        other_client = ClientSite.objects.create(name="Other client", domain="other-client.test")
        other_placement = Placement.objects.create(donor=other_donor, client=other_client, position=1)
        response = self.client.post(
            reverse("placements-reorder"),
            json.dumps({"ids": [self.placements[0].pk, other_placement.pk]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_add_does_not_duplicate_existing_placement(self):
        response = self.client.post(
            reverse("placement-add", args=[self.donor.pk]),
            {"client_id": self.clients[0].pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Placement.objects.filter(donor=self.donor, client=self.clients[0]).count(),
            1,
        )

    def test_archived_client_cannot_be_added(self):
        archived = ClientSite.objects.create(name="Archived", domain="archived.test", enabled=False)
        response = self.client.post(
            reverse("placement-add", args=[self.donor.pk]),
            {"client_id": archived.pk},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Placement.objects.filter(donor=self.donor, client=archived).exists())

    def test_anonymous_user_is_redirected(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)


class TemplateViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("template-operator", password="test")
        self.client.force_login(self.user)
        self.first = PageTemplate.objects.create(name="First", slug="first")
        self.second = PageTemplate.objects.create(name="Second", slug="second")
        DonorSite.objects.create(
            name="D",
            domain="template-donor.test",
            admin_url="https://template-donor.test/admin",
            page_url="https://template-donor.test/p",
            template=self.second,
        )

    def test_template_list_contains_all_templates_and_usage_count(self):
        response = self.client.get(reverse("template-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "First")
        self.assertContains(response, "Second")
        second = next(item for item in response.context["templates"] if item.pk == self.second.pk)
        self.assertEqual(second.donor_count, 1)

    def test_specific_template_can_be_edited_without_touching_first(self):
        response = self.client.post(
            reverse("template-edit", args=[self.second.pk]),
            {
                "name": "Second updated",
                "slug": "second",
                "wrapper_html": self.second.wrapper_html,
                "item_html": self.second.item_html,
                "css": ".partners{display:grid}",
                "include_css_in_article": "on",
                "enabled": "on",
                "version": 2,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.assertEqual(self.first.name, "First")
        self.assertEqual(self.second.name, "Second updated")
        self.assertEqual(self.second.version, 2)
        self.assertTrue(self.second.include_css_in_article)


class PublicMediaTests(TestCase):
    def test_media_is_publicly_readable_with_debug_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            media_root = Path(directory)
            logo_dir = media_root / "client_logos"
            logo_dir.mkdir()
            (logo_dir / "logo.webp").write_bytes(b"RIFFfake-webp")

            with override_settings(MEDIA_ROOT=media_root, DEBUG=False):
                response = self.client.get("/media/client_logos/logo.webp")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "image/webp")
                self.assertEqual(response["Cache-Control"], "public, max-age=86400")
                self.assertEqual(b"".join(response.streaming_content), b"RIFFfake-webp")

    def test_missing_media_returns_404(self):
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(MEDIA_ROOT=Path(directory), DEBUG=False):
                response = self.client.get("/media/client_logos/missing.webp")
                self.assertEqual(response.status_code, 404)
