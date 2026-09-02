import os
from django.test import TestCase, override_settings
from partners.forms import DonorForm
from partners.models import ClientSite, DonorSite, PageTemplate, Placement
from partners.services.credentials import decrypt_password, encrypt_password
from partners.services.page_renderer import has_managed_marker, render_page

class RendererTests(TestCase):
    def setUp(self):
        self.template = PageTemplate.objects.create(name="Test", slug="test-renderer", wrapper_html="<ul>{{ items }}</ul>", item_html='<li><a href="{{ url }}"{{ link_attributes }}><img src="{{ image }}" alt="{{ client_name }}">{{ client_html }}</a></li>', css=".x{}", include_css_in_article=True)
        self.donor = DonorSite.objects.create(name="Donor", domain="donor.test", admin_url="https://donor.test/administrator/", page_url="https://donor.test/partners", template=self.template)
        self.one = ClientSite.objects.create(name="One & Co", domain="one.test", default_html="<b>ONE</b>")
        self.two = ClientSite.objects.create(name="Two", domain="two.test", default_html="TWO")

    def test_order_override_disabled_attributes_marker_and_hash(self):
        Placement.objects.create(donor=self.donor, client=self.one, position=20, target_blank=True, nofollow=True, sponsored=True)
        Placement.objects.create(donor=self.donor, client=self.two, position=10, html_override="OVERRIDE", enabled=True)
        disabled = ClientSite.objects.create(name="Off", domain="off.test", default_html="MUST NOT APPEAR")
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

    def test_disabled_client_is_ignored(self):
        self.one.enabled = False; self.one.save()
        Placement.objects.create(donor=self.donor, client=self.one)
        self.assertNotIn("ONE", render_page(self.donor).body_html)

class CredentialTests(TestCase):
    def test_round_trip_and_form_never_contains_existing_secret(self):
        os.environ["CREDENTIAL_ENCRYPTION_KEY"] = "unit-test-key"
        encrypted = encrypt_password("super-secret")
        self.assertNotIn("super-secret", encrypted)
        self.assertEqual(decrypt_password(encrypted), "super-secret")
        donor = DonorSite(name="D", domain="d.test", admin_url="https://d.test/admin", page_url="https://d.test/p", encrypted_password=encrypted)
        html = DonorForm(instance=donor).as_p()
        self.assertNotIn("super-secret", html)
        self.assertNotIn(encrypted, html)
