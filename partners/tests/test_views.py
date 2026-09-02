import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from partners.models import ClientSite, DonorSite, Placement

class PlacementViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("operator", password="test")
        self.client.force_login(self.user)
        self.donor = DonorSite.objects.create(name="D", domain="d.test", admin_url="https://d.test/admin", page_url="https://d.test/p")
        self.clients = [ClientSite.objects.create(name=f"C{i}", domain=f"c{i}.test") for i in range(3)]
        self.placements = [Placement.objects.create(donor=self.donor, client=c, position=i) for i, c in enumerate(self.clients)]

    def test_reorder_and_toggle(self):
        ids = [p.pk for p in reversed(self.placements)]
        response = self.client.post(reverse("placements-reorder"), json.dumps({"ids": ids}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(self.donor.placements.values_list("pk", flat=True)), ids)
        response = self.client.post(reverse("placement-toggle", args=[ids[0]]))
        self.assertFalse(response.json()["enabled"])

    def test_anonymous_user_is_redirected(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

