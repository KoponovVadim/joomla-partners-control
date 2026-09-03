from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from partners.models import ClientSite, DonorSite, Placement


class ClientColorMarkersTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("color-operator", password="test")
        self.client.force_login(user)
        donor = DonorSite.objects.create(
            name="Color donor",
            domain="color-donor.test",
            admin_url="https://color-donor.test/administrator/",
            page_url="https://color-donor.test/nashi-partnery",
        )
        parasite = ClientSite.objects.create(
            name="Stable client",
            domain="https://stable-client.test/",
        )
        Placement.objects.create(donor=donor, client=parasite, position=1)

    def test_dashboard_exposes_stable_client_key_in_matrix_and_details(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'data-client-key="https://stable-client.test/"',
            count=2,
        )
