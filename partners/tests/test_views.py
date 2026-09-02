import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from partners.models import ClientSite, DonorSite, Placement


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
