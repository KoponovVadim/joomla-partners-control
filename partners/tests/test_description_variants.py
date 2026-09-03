from django.test import TestCase

from partners.models import (
    ClientDescriptionVariant,
    ClientSite,
    DonorSite,
    Placement,
)
from partners.services.page_renderer import _description_for_placement


class ClientDescriptionVariantTests(TestCase):
    def setUp(self):
        self.client = ClientSite.objects.create(
            name="Hydrotact",
            domain="https://hydrotact.ru",
            description="Legacy description",
        )
        self.variant_a = ClientDescriptionVariant.objects.create(
            client=self.client,
            name="Основное",
            text="Первый вариант описания",
            position=1,
        )
        self.variant_b = ClientDescriptionVariant.objects.create(
            client=self.client,
            name="Нейтральное",
            text="Второй вариант описания",
            position=2,
        )
        self.donor = DonorSite.objects.create(
            name="Donor A",
            domain="donor-a.test",
            admin_url="https://donor-a.test/administrator/",
            page_url="https://donor-a.test/partners",
        )
        self.placement = Placement.objects.create(
            donor=self.donor,
            client=self.client,
        )

    def test_auto_variant_is_stable_for_same_donor(self):
        first = _description_for_placement(self.placement)
        second = _description_for_placement(
            Placement.objects.select_related("donor", "client", "description_variant")
            .prefetch_related("client__description_variants")
            .get(pk=self.placement.pk)
        )

        self.assertIn(first, {self.variant_a.text, self.variant_b.text})
        self.assertEqual(first, second)

    def test_pinned_variant_wins_over_auto_selection(self):
        self.placement.description_variant = self.variant_b
        self.placement.save(update_fields=["description_variant"])

        self.assertEqual(
            _description_for_placement(self.placement),
            self.variant_b.text,
        )

    def test_manual_donor_override_has_highest_priority(self):
        self.placement.description_variant = self.variant_b
        self.placement.description_override = "Уникальный текст только для этого донора"
        self.placement.save(update_fields=["description_variant", "description_override"])

        self.assertEqual(
            _description_for_placement(self.placement),
            "Уникальный текст только для этого донора",
        )

    def test_disabled_pinned_variant_is_not_used(self):
        self.variant_b.enabled = False
        self.variant_b.save(update_fields=["enabled"])
        self.placement.description_variant = self.variant_b
        self.placement.save(update_fields=["description_variant"])

        self.assertEqual(
            _description_for_placement(self.placement),
            self.variant_a.text,
        )

    def test_legacy_description_is_fallback_without_variants(self):
        self.client.description_variants.all().delete()

        self.assertEqual(
            _description_for_placement(self.placement),
            "Legacy description",
        )
