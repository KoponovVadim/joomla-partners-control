from datetime import timedelta
from unittest.mock import Mock

import httpx
from django.test import TestCase
from django.utils import timezone

from partners.models import DonorSite
from partners.services.page_health import check_donor_page


class PageHealthTests(TestCase):
    def setUp(self):
        self.donor = DonorSite.objects.create(
            name="Donor",
            domain="donor.test",
            admin_url="https://donor.test/administrator/",
            page_url="https://donor.test/partners",
        )

    def test_404_sets_unhealthy_since_and_keeps_original_date(self):
        client = Mock()
        client.get.return_value = Mock(status_code=404)
        first = timezone.now()
        second = first + timedelta(hours=2)

        check_donor_page(self.donor, client=client, checked_at=first)
        self.donor.refresh_from_db()
        self.assertEqual(self.donor.page_http_status, 404)
        self.assertEqual(self.donor.page_unhealthy_since, first)
        self.assertEqual(self.donor.page_health_state, "not_found")

        check_donor_page(self.donor, client=client, checked_at=second)
        self.donor.refresh_from_db()
        self.assertEqual(self.donor.page_unhealthy_since, first)
        self.assertEqual(self.donor.page_checked_at, second)

    def test_success_clears_unhealthy_since(self):
        self.donor.page_http_status = 404
        self.donor.page_checked_at = timezone.now() - timedelta(hours=1)
        self.donor.page_unhealthy_since = self.donor.page_checked_at
        self.donor.save()

        client = Mock()
        client.get.return_value = Mock(status_code=200)
        checked_at = timezone.now()
        check_donor_page(self.donor, client=client, checked_at=checked_at)

        self.donor.refresh_from_db()
        self.assertEqual(self.donor.page_http_status, 200)
        self.assertIsNone(self.donor.page_unhealthy_since)
        self.assertEqual(self.donor.page_health_state, "ok")

    def test_network_error_is_recorded(self):
        client = Mock()
        client.get.side_effect = httpx.ConnectError("connection refused")

        check_donor_page(self.donor, client=client)

        self.donor.refresh_from_db()
        self.assertIsNone(self.donor.page_http_status)
        self.assertIn("connection refused", self.donor.page_check_error)
        self.assertEqual(self.donor.page_health_state, "error")
