from io import BytesIO
import tempfile
from pathlib import Path

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from partners.models import ClientSite, DonorSite, PageTemplate, Placement
from partners.services.page_renderer import render_page


class DirectLogoUploadTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("logo-operator", password="test")
        self.client.force_login(self.user)
        self.template = PageTemplate.objects.create(
            name="Partners with logo",
            slug="partners-with-logo",
            wrapper_html='<ul class="partners">{{ items }}</ul>',
            item_html='<li><a href="{{ url }}"><img src="{{ image }}" alt="{{ client_name }}"></a>{{ client_html }}</li>',
        )
        self.donor = DonorSite.objects.create(
            name="Donor",
            domain="donor-logo.test",
            admin_url="https://donor-logo.test/administrator/",
            page_url="https://donor-logo.test/partners",
            template=self.template,
        )

    def _png_upload(self, name="client-logo.png"):
        buffer = BytesIO()
        Image.new("RGB", (24, 16), "white").save(buffer, format="PNG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")

    def test_uploaded_image_from_client_form_is_saved_and_used_in_article_html(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(
            MEDIA_ROOT=Path(directory),
            PUBLIC_BASE_URL="https://parasyte.deluxmedia.ru",
            DEBUG=False,
        ):
            response = self.client.post(
                reverse("client-create"),
                {
                    "name": "Client with uploaded logo",
                    "domain": "client-upload.test",
                    "default_html": "Партнёр с загруженной картинкой",
                    "notes": "",
                    "enabled": "on",
                    "logo": self._png_upload(),
                },
            )
            self.assertEqual(response.status_code, 302)

            client = ClientSite.objects.get(domain="client-upload.test")
            self.assertTrue(client.logo.name.startswith("client_logos/"))
            self.assertTrue((Path(directory) / client.logo.name).is_file())

            Placement.objects.create(donor=self.donor, client=client, position=1)
            page = render_page(self.donor)
            expected_url = f"https://parasyte.deluxmedia.ru{client.logo.url}"

            self.assertIn(f'src="{expected_url}"', page.final_html)
            self.assertIn("Партнёр с загруженной картинкой", page.final_html)

            media_response = self.client.get(client.logo.url)
            self.assertEqual(media_response.status_code, 200)
            self.assertEqual(media_response["Content-Type"], "image/png")

    @override_settings(PUBLIC_BASE_URL="", DEBUG=False)
    def test_production_render_stops_if_uploaded_logo_has_no_public_base_url(self):
        client = ClientSite.objects.create(
            name="Unsafe relative logo",
            domain="unsafe-logo.test",
            logo="client_logos/unsafe.png",
        )
        Placement.objects.create(donor=self.donor, client=client, position=1)
        with self.assertRaisesRegex(ValueError, "PUBLIC_BASE_URL"):
            render_page(self.donor)

    def test_client_form_explains_that_uploaded_logo_is_used_automatically(self):
        client = ClientSite.objects.create(name="Existing", domain="existing-logo.test")
        response = self.client.get(reverse("client-edit", args=[client.pk]))
        self.assertContains(response, "Эта картинка пойдёт в статью автоматически")
        self.assertContains(response, "JPG, PNG, WebP или GIF до 8 МБ")
