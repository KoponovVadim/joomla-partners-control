from django.test import TestCase

from partners.models import (
    ClientDescriptionVariant,
    ClientSite,
    DonorSite,
    PageTemplate,
    Placement,
)
from partners.services.page_renderer import _variant_html_for_placement, render_page


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
            html='<p>Первый вариант <a href="https://hydrotact.ru/a">A</a></p>',
            position=1,
        )
        self.variant_b = ClientDescriptionVariant.objects.create(
            client=self.client,
            name="Нейтральное",
            html='<p>Второй вариант <a href="/b">B</a> и <a href="https://hydrotact.ru/c">C</a></p>',
            position=2,
        )
        self.template = PageTemplate.objects.create(
            name="Test",
            slug="test-html-variants",
            wrapper_html='<ul class="partners">{{ items }}</ul>',
            item_html='<li><a href="{{ url }}"><img src="{{ image }}" alt="{{ client_name }}"></a><div>{{ client_html }}</div></li>',
        )
        self.donor = DonorSite.objects.create(
            name="Donor A",
            domain="donor-a.test",
            admin_url="https://donor-a.test/administrator/",
            page_url="https://donor-a.test/partners",
            template=self.template,
        )
        self.placement = Placement.objects.create(
            donor=self.donor,
            client=self.client,
        )

    def test_auto_variant_is_stable_for_same_donor(self):
        first = _variant_html_for_placement(self.placement)
        second = _variant_html_for_placement(
            Placement.objects.select_related("donor", "client", "description_variant")
            .prefetch_related("client__description_variants")
            .get(pk=self.placement.pk)
        )

        self.assertIn(first, {self.variant_a.html, self.variant_b.html})
        self.assertEqual(first, second)

    def test_pinned_variant_wins_over_auto_selection(self):
        self.placement.description_variant = self.variant_b
        self.placement.save(update_fields=["description_variant"])

        self.assertEqual(_variant_html_for_placement(self.placement), self.variant_b.html)

    def test_disabled_pinned_variant_is_not_used(self):
        self.variant_b.enabled = False
        self.variant_b.save(update_fields=["enabled"])
        self.placement.description_variant = self.variant_b
        self.placement.save(update_fields=["description_variant"])

        self.assertEqual(_variant_html_for_placement(self.placement), self.variant_a.html)

    def test_html_variant_preserves_multiple_text_links(self):
        self.placement.description_variant = self.variant_b
        self.placement.save(update_fields=["description_variant"])

        page = render_page(self.donor)

        self.assertIn('href="https://hydrotact.ru/b"', page.final_html)
        self.assertIn('href="https://hydrotact.ru/c"', page.final_html)
        self.assertIn("Второй вариант", page.final_html)

    def test_html_override_wins_over_variant(self):
        self.placement.description_variant = self.variant_b
        self.placement.html_override = '<p>Только здесь <a href="https://hydrotact.ru/special">special</a></p>'
        self.placement.save(update_fields=["description_variant", "html_override"])

        page = render_page(self.donor)

        self.assertIn("Только здесь", page.final_html)
        self.assertNotIn("Второй вариант", page.final_html)
