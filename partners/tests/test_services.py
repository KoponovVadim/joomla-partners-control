import os

from bs4 import BeautifulSoup
from django.test import TestCase, override_settings

from partners.forms import DonorForm
from partners.models import ClientSite, DonorSite, PageTemplate, Placement
from partners.services.credentials import decrypt_password, encrypt_password
from partners.services.page_renderer import has_managed_marker, render_page


class RendererTests(TestCase):
    def setUp(self):
        self.template = PageTemplate.objects.create(
            name="Test",
            slug="test-renderer",
            wrapper_html="<ul>{{ items }}</ul>",
            item_html=(
                '<li><div class="Img"><a href="{{ url }}"{{ link_attributes }}>'
                '<img src="{{ image }}" alt="{{ client_name }}"></a></div>'
                '<div class="txt">{{ client_html }}</div></li>'
            ),
            css=".x{}",
            include_css_in_article=True,
        )
        self.donor = DonorSite.objects.create(
            name="Donor",
            domain="donor.test",
            admin_url="https://donor.test/administrator/",
            page_url="https://donor.test/partners",
            template=self.template,
        )
        self.one = ClientSite.objects.create(name="One & Co", domain="one.test", default_html="<b>ONE</b>")
        self.two = ClientSite.objects.create(name="Two", domain="two.test", default_html="TWO")

    def test_order_override_disabled_attributes_marker_and_hash(self):
        Placement.objects.create(
            donor=self.donor,
            client=self.one,
            position=20,
            target_blank=True,
            nofollow=True,
            sponsored=True,
        )
        Placement.objects.create(
            donor=self.donor,
            client=self.two,
            position=10,
            html_override="OVERRIDE",
            enabled=True,
        )
        disabled = ClientSite.objects.create(
            name="Off",
            domain="off.test",
            default_html="MUST NOT APPEAR",
        )
        Placement.objects.create(donor=self.donor, client=disabled, position=1, enabled=False)
        page = render_page(self.donor)
        self.assertLess(page.body_html.index("OVERRIDE"), page.body_html.index("<b>ONE</b>"))
        self.assertNotIn("MUST NOT APPEAR", page.body_html)
        self.assertIn('target="_blank"', page.body_html)
        self.assertIn('rel="noopener nofollow sponsored"', page.body_html)
        self.assertIn("<style>", page.final_html)
        self.assertTrue(has_managed_marker(page.body_html, self.donor))
        self.assertEqual(len(page.body_hash), 64)
        self.assertIn("One &amp; Co", page.body_html)
        items = BeautifulSoup(page.body_html, "html.parser").select("ul > li")
        self.assertEqual(len(items), 2)
        self.assertTrue(all(len(item.find_all("a")) == 2 for item in items))

    def test_plain_description_is_escaped_and_gets_exactly_one_text_link(self):
        client = ClientSite.objects.create(
            name="Safe & Co",
            domain="safe.test",
            description="Builds <strong>sites</strong>\nFast & safe",
            link_text="Visit & learn",
        )
        Placement.objects.create(
            donor=self.donor,
            client=client,
            target_blank=True,
            nofollow=True,
        )

        page = render_page(self.donor)
        item = BeautifulSoup(page.body_html, "html.parser").select_one("li")
        image_link = item.select_one(".Img > a")
        text_link = item.select_one(".txt a")

        self.assertEqual(len(item.find_all("a")), 2)
        self.assertEqual(image_link["href"], "https://safe.test")
        self.assertEqual(text_link["href"], "https://safe.test")
        self.assertEqual(text_link.get_text(strip=True), "Visit & learn")
        self.assertEqual(image_link["target"], "_blank")
        self.assertEqual(text_link["target"], "_blank")
        self.assertEqual(text_link["rel"], ["noopener", "nofollow"])
        self.assertNotIn("<strong>", str(item.select_one(".txt")))
        self.assertIn("&lt;strong&gt;", str(item.select_one(".txt")))
        self.assertIn("<br", str(item.select_one(".txt")))

    def test_advanced_html_keeps_content_but_normalizes_to_one_text_link(self):
        self.one.default_html = (
            '<p>See <a href="https://old.test/one">first</a> and '
            '<a href="https://old.test/two">second</a>.</p>'
        )
        self.one.save(update_fields=["default_html"])
        Placement.objects.create(donor=self.donor, client=self.one)

        item = BeautifulSoup(render_page(self.donor).body_html, "html.parser").select_one("li")
        text_links = [link for link in item.find_all("a") if link.find("img") is None]

        self.assertEqual(len(item.find_all("a")), 2)
        self.assertEqual(len(text_links), 1)
        self.assertEqual(text_links[0]["href"], "https://one.test")
        self.assertIn("first", item.get_text(" ", strip=True))
        self.assertIn("second", item.get_text(" ", strip=True))

    def test_invalid_item_template_is_blocked_before_sync(self):
        self.template.item_html = (
            '<li><div class="Img"><img src="{{ image }}" alt="{{ client_name }}"></div>'
            '<div class="txt">{{ client_html }}</div></li>'
        )
        self.template.save(update_fields=["item_html"])
        Placement.objects.create(donor=self.donor, client=self.one)

        with self.assertRaisesRegex(ValueError, "ровно две"):
            render_page(self.donor)

    def test_disabled_client_is_ignored(self):
        self.one.enabled = False
        self.one.save()
        Placement.objects.create(donor=self.donor, client=self.one)
        self.assertNotIn("ONE", render_page(self.donor).body_html)

    @override_settings(PUBLIC_BASE_URL="https://parasyte.deluxmedia.ru")
    def test_uploaded_logo_is_rendered_as_absolute_public_url(self):
        self.one.logo = "client_logos/one.webp"
        self.one.save(update_fields=["logo"])
        Placement.objects.create(donor=self.donor, client=self.one)
        page = render_page(self.donor)
        self.assertIn(
            'src="https://parasyte.deluxmedia.ru/media/client_logos/one.webp"',
            page.body_html,
        )

    @override_settings(PUBLIC_BASE_URL="https://parasyte.deluxmedia.ru")
    def test_relative_image_override_is_rendered_as_absolute_public_url(self):
        Placement.objects.create(
            donor=self.donor,
            client=self.one,
            image_override="/partners/one.webp",
        )
        page = render_page(self.donor)
        self.assertIn('src="https://parasyte.deluxmedia.ru/partners/one.webp"', page.body_html)

    @override_settings(PUBLIC_BASE_URL="https://parasyte.deluxmedia.ru")
    def test_absolute_image_override_is_preserved(self):
        Placement.objects.create(
            donor=self.donor,
            client=self.one,
            image_override="https://cdn.example.test/one.webp",
        )
        page = render_page(self.donor)
        self.assertIn('src="https://cdn.example.test/one.webp"', page.body_html)


class CredentialTests(TestCase):
    def test_round_trip_and_form_never_contains_existing_secret(self):
        os.environ["CREDENTIAL_ENCRYPTION_KEY"] = "unit-test-key"
        encrypted = encrypt_password("super-secret")
        self.assertNotIn("super-secret", encrypted)
        self.assertEqual(decrypt_password(encrypted), "super-secret")
        donor = DonorSite(
            name="D",
            domain="d.test",
            admin_url="https://d.test/admin",
            page_url="https://d.test/p",
            encrypted_password=encrypted,
        )
        html = DonorForm(instance=donor).as_p()
        self.assertNotIn("super-secret", html)
        self.assertNotIn(encrypted, html)
