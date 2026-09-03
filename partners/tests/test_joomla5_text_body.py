from django.test import SimpleTestCase

from partners.joomla.joomla5 import Joomla5Adapter


class Joomla5TextBodyTests(SimpleTestCase):
    uuid = "a7b3c4b9-f6fa-4411-a6f2-10e8254441e6"

    def resource(self, text):
        return {
            "type": "articles",
            "id": "2",
            "attributes": {
                "id": 2,
                "title": "Наши партнеры",
                "alias": "nashi-partnery",
                "text": text,
            },
        }

    def test_joomla5_reads_real_body_from_text_attribute(self):
        span = f'<span id="jpc-managed-page-{self.uuid}" hidden></span>\n<ul></ul>'

        article = Joomla5Adapter._article_from_resource(self.resource(span))

        self.assertEqual(article.article_id, 2)
        self.assertIn(
            f"<!-- JPC-MANAGED-PAGE:{self.uuid} -->",
            article.body_html,
        )
        self.assertIn("<ul></ul>", article.body_html)
        self.assertNotIn("jpc-managed-page-", article.body_html)

    def test_marker_parser_accepts_joomla_attribute_serialization(self):
        span = (
            f'<span class="marker" hidden="" '
            f'id="jpc-managed-page-{self.uuid}"></span>'
        )

        article = Joomla5Adapter._article_from_resource(self.resource(span))

        self.assertEqual(
            article.body_html,
            f"<!-- JPC-MANAGED-PAGE:{self.uuid} -->",
        )
