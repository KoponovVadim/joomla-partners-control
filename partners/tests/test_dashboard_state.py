from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from partners.models import DonorSite


class DashboardStateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("dashboard-operator", password="test")
        self.client.force_login(self.user)
        self.donor = DonorSite.objects.create(
            name="Persistent donor",
            domain="persistent.test",
            admin_url="https://persistent.test/administrator/",
            page_url="https://persistent.test/nashi-partnery",
        )

    def test_donor_row_exposes_id_for_expansion_state_restore(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-donor-id="{self.donor.pk}"')
        self.assertContains(response, f'aria-controls="donor-detail-{self.donor.pk}"')
        self.assertContains(response, "partners/dashboard.js")
