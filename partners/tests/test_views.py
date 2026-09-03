import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from partners.models import (
    ArticleSnapshot,
    ClientSite,
    DonorSite,
    PageTemplate,
    Placement,
    PublicationLog,
)
from partners.services.credentials import decrypt_secret


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


class DonorAuthViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "api-operator",
            password="test",
        )
        self.client.force_login(self.user)
        self.env = patch.dict(
            os.environ,
            {"CREDENTIAL_ENCRYPTION_KEY": "view-api-token-tests"},
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_create_joomla5_donor_encrypts_api_token(self):
        response = self.client.post(
            reverse("donor-create"),
            {
                "name": "Joomla 5 donor",
                "domain": "j5.test",
                "admin_url": "https://j5.test/administrator/",
                "page_url": "https://j5.test/partners",
                "joomla_version": DonorSite.JoomlaVersion.V5,
                "auth_mode": DonorSite.AuthMode.API_TOKEN,
                "username": "",
                "password": "",
                "api_url": "",
                "api_token": "plain-api-token",
                "article_id": "",
                "article_title": "Partners",
                "article_category_id": "2",
                "menu_item_id": "",
                "article_alias": "partners",
                "template": "",
                "enabled": "on",
                "notes": "",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        donor = DonorSite.objects.get(domain="j5.test")
        self.assertNotIn("plain-api-token", donor.encrypted_api_token)
        self.assertEqual(
            decrypt_secret(donor.encrypted_api_token),
            "plain-api-token",
        )

        edit = self.client.get(reverse("donor-edit", args=[donor.pk]))
        self.assertNotContains(edit, "plain-api-token")
        self.assertNotContains(edit, donor.encrypted_api_token)
        self.assertContains(edit, "API Token сохранён в зашифрованном виде")


class SnapshotViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("snapshot-operator", password="test")
        self.client.force_login(self.user)
        self.donor = DonorSite.objects.create(
            name="Snapshot donor",
            domain="snapshot.test",
            admin_url="https://snapshot.test/administrator/",
            page_url="https://snapshot.test/partners",
            joomla_version="3",
            article_id=87,
        )
        self.marker = f"<!-- JPC-MANAGED-PAGE:{self.donor.managed_marker_uuid} -->"
        self.snapshot = ArticleSnapshot.objects.create(
            donor=self.donor,
            article_id=87,
            title="Partners",
            body_html=self.marker + "\n<ul><li>old</li></ul>",
            body_hash="a" * 64,
            reason="before_update",
        )

    def test_snapshot_preview_is_scoped_to_donor(self):
        response = self.client.get(reverse("donor-snapshot", args=[self.donor.pk, self.snapshot.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Snapshot #")
        self.assertContains(response, "old")

        other = DonorSite.objects.create(
            name="Other donor",
            domain="other-snapshot.test",
            admin_url="https://other-snapshot.test/administrator/",
            page_url="https://other-snapshot.test/partners",
        )
        response = self.client.get(reverse("donor-snapshot", args=[other.pk, self.snapshot.pk]))
        self.assertEqual(response.status_code, 404)

    def test_managed_snapshot_can_be_restored(self):
        adapter = Mock()
        adapter.update_article.return_value = "Материал #87 обновлён; backup snapshot #99"
        with patch("partners.views.get_adapter", return_value=adapter):
            response = self.client.post(
                reverse("donor-restore-snapshot", args=[self.donor.pk, self.snapshot.pk])
            )

        self.assertRedirects(response, reverse("donor-edit", args=[self.donor.pk]))
        adapter.update_article.assert_called_once_with(87, self.snapshot.body_html)
        self.donor.refresh_from_db()
        self.assertIsNotNone(self.donor.last_published_at)
        log = PublicationLog.objects.get(action="restore_snapshot")
        self.assertEqual(log.status, "success")
        self.assertEqual(log.generated_html_hash, self.snapshot.body_hash)
        self.assertIn(f"Snapshot #{self.snapshot.pk} восстановлен", log.message)

    def test_joomla5_managed_snapshot_can_be_restored(self):
        self.donor.joomla_version = DonorSite.JoomlaVersion.V5
        self.donor.save(update_fields=["joomla_version"])
        adapter = Mock()
        adapter.update_article.return_value = "Joomla 5 API restored"

        with patch("partners.views.get_adapter", return_value=adapter):
            response = self.client.post(
                reverse(
                    "donor-restore-snapshot",
                    args=[self.donor.pk, self.snapshot.pk],
                )
            )

        self.assertRedirects(response, reverse("donor-edit", args=[self.donor.pk]))
        adapter.update_article.assert_called_once_with(87, self.snapshot.body_html)
        self.assertEqual(
            PublicationLog.objects.get(action="restore_snapshot").status,
            "success",
        )

    def test_before_adoption_snapshot_is_preview_only(self):
        original = ArticleSnapshot.objects.create(
            donor=self.donor,
            article_id=87,
            title="Original",
            body_html="<p>Original unmanaged HTML</p>",
            body_hash="b" * 64,
            reason="before_adoption",
        )
        with patch("partners.views.get_adapter") as get_adapter:
            response = self.client.post(
                reverse("donor-restore-snapshot", args=[self.donor.pk, original.pk])
            )

        self.assertRedirects(
            response,
            reverse("donor-snapshot", args=[self.donor.pk, original.pk]),
        )
        get_adapter.assert_not_called()
        self.assertFalse(PublicationLog.objects.filter(action="restore_snapshot").exists())

    def test_snapshot_for_old_article_id_cannot_be_restored(self):
        old_article = ArticleSnapshot.objects.create(
            donor=self.donor,
            article_id=12,
            body_html=self.marker + "\n<p>old article</p>",
            body_hash="c" * 64,
        )
        with patch("partners.views.get_adapter") as get_adapter:
            response = self.client.post(
                reverse("donor-restore-snapshot", args=[self.donor.pk, old_article.pk])
            )
        self.assertRedirects(response, reverse("donor-edit", args=[self.donor.pk]))
        get_adapter.assert_not_called()


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

    def test_non_logo_media_is_not_public(self):
        with tempfile.TemporaryDirectory() as directory:
            media_root = Path(directory)
            (media_root / "secret.txt").write_text("not public", encoding="utf-8")
            with override_settings(MEDIA_ROOT=media_root, DEBUG=False):
                response = self.client.get("/media/secret.txt")
                self.assertEqual(response.status_code, 404)

    def test_non_image_inside_logo_directory_is_not_public(self):
        with tempfile.TemporaryDirectory() as directory:
            media_root = Path(directory)
            logo_dir = media_root / "client_logos"
            logo_dir.mkdir()
            (logo_dir / "secret.txt").write_text("not an image", encoding="utf-8")
            with override_settings(MEDIA_ROOT=media_root, DEBUG=False):
                response = self.client.get("/media/client_logos/secret.txt")
                self.assertEqual(response.status_code, 404)

    def test_logo_path_cannot_traverse_to_other_media(self):
        with tempfile.TemporaryDirectory() as directory:
            media_root = Path(directory)
            (media_root / "client_logos").mkdir()
            (media_root / "secret.webp").write_bytes(b"private")
            with override_settings(MEDIA_ROOT=media_root, DEBUG=False):
                response = self.client.get(
                    "/media/client_logos/../secret.webp",
                )
                self.assertEqual(response.status_code, 404)


class ProductionSecurityTests(TestCase):
    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_HSTS_SECONDS=31536000,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
    )
    def test_proxy_https_is_trusted_and_security_headers_are_set(self):
        response = self.client.get(
            reverse("login"),
            HTTP_X_FORWARDED_PROTO="https",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Strict-Transport-Security"],
            "max-age=31536000",
        )
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertTrue(response.cookies["csrftoken"]["secure"])
