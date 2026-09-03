from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from partners.models import ClientSite, DonorSite, Placement


class ClientHtmlUiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("ui-operator", password="test")
        self.client.force_login(self.user)
        self.partner = ClientSite.objects.create(
            name="Аргторг",
            domain="https://argtorg.ru/",
        )
        self.donor = DonorSite.objects.create(
            name="Street Wall",
            domain="street-wall.ru",
            admin_url="https://street-wall.ru/administrator/",
            page_url="https://street-wall.ru/nashi-partnery",
        )
        Placement.objects.create(donor=self.donor, client=self.partner)

    def test_client_editor_uses_html_variants_without_preview_or_legacy_fields(self):
        response = self.client.get(reverse("client-edit", args=[self.partner.pk]))

        self.assertContains(response, "Варианты HTML-описания")
        self.assertNotContains(response, "Предпросмотр описания")
        self.assertNotContains(response, ">Текст ссылки<")
        self.assertNotContains(response, ">Расширенный HTML<")
        self.assertNotContains(response, ">Заметки<")

    def test_client_mode_links_to_donor_and_exact_partner_page(self):
        response = self.client.get(reverse("dashboard") + "?mode=clients")

        self.assertContains(response, 'href="https://street-wall.ru"', html=False)
        self.assertContains(response, 'href="https://street-wall.ru/nashi-partnery"', html=False)

    def test_donor_matrix_shows_404_since_date(self):
        self.donor.page_http_status = 404
        self.donor.page_checked_at = timezone.now()
        self.donor.page_unhealthy_since = timezone.now()
        self.donor.save()

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "404 с")
        self.assertContains(response, "Статус страницы")
        self.assertNotContains(response, "Последняя публикация")
