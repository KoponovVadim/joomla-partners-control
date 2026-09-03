from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from partners.forms import DonorForm
from partners.models import DonorSite


class DonorTopicUiTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="topic-admin", password="test-pass")
        self.client.force_login(user)
        self.donor = DonorSite.objects.create(
            name="Аргторг",
            domain="argtorg.ru",
            topic="Дорожное строительство",
            admin_url="https://argtorg.ru/administrator/",
            page_url="https://argtorg.ru/nashi-partnery",
        )

    def test_donor_form_exposes_topic_field(self):
        form = DonorForm(instance=self.donor)
        self.assertIn("topic", form.fields)
        self.assertEqual(form.fields["topic"].label, "Тематика сайта")

    def test_dashboard_exposes_topic_for_search_and_filter(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Дорожное строительство")
        self.assertContains(response, 'data-donor-topic="дорожное строительство"')
        self.assertContains(response, "data-donor-topic-filter")

    def test_client_editor_uses_full_workspace_width(self):
        css = (Path(settings.BASE_DIR) / "static" / "partners" / "client-variants.css").read_text()
        self.assertIn(".client-form-layout{max-width:none}", css)
        self.assertIn("grid-template-columns:170px minmax(0,1fr) 120px", css)
