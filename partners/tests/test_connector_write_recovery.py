from unittest.mock import Mock, patch

from django.test import TestCase

from partners.joomla.exceptions import JoomlaArticleError
from partners.joomla.joomla3_connector import (
    Joomla3ConnectorAdapter,
    JoomlaConnectorArticle,
)
from partners.models import DonorSite


class ConnectorWriteRecoveryTests(TestCase):
    def setUp(self):
        self.donor = DonorSite.objects.create(
            name="Recovery donor",
            domain="recovery.test",
            admin_url="https://recovery.test/administrator/",
            page_url="https://recovery.test/nashi-partnery",
        )
        self.adapter = Joomla3ConnectorAdapter(self.donor)
        self.client = Mock()

    def test_write_error_is_recovered_when_remote_body_matches(self):
        html = "<!-- JPC-MANAGED-PAGE:test -->\n<ul><li>new</li></ul>"
        verified = JoomlaConnectorArticle(
            article_id=46,
            title="Partners",
            alias="partners",
            body_html=html,
        )

        with patch.object(
            self.adapter,
            "_command",
            side_effect=JoomlaArticleError(
                "JPC Connector вернул HTTP 500: Unknown column 'alias' in 'field list'"
            ),
        ), patch.object(
            self.adapter,
            "_get_article",
            return_value=verified,
        ):
            article, recovered = self.adapter._write_and_verify(
                self.client,
                "update",
                46,
                html,
                marker_uuid="test",
                expected_hash="a" * 64,
            )

        self.assertTrue(recovered)
        self.assertEqual(article.body_html, html)

    def test_write_error_remains_failure_when_remote_body_does_not_match(self):
        requested_html = "<p>new</p>"
        verified = JoomlaConnectorArticle(
            article_id=46,
            title="Partners",
            alias="partners",
            body_html="<p>old</p>",
        )
        write_error = JoomlaArticleError(
            "JPC Connector вернул HTTP 500: Unknown column 'alias' in 'field list'"
        )

        with patch.object(
            self.adapter,
            "_command",
            side_effect=write_error,
        ), patch.object(
            self.adapter,
            "_get_article",
            return_value=verified,
        ):
            with self.assertRaises(JoomlaArticleError) as caught:
                self.adapter._write_and_verify(
                    self.client,
                    "update",
                    46,
                    requested_html,
                    marker_uuid="test",
                    expected_hash="a" * 64,
                )

        self.assertIs(caught.exception, write_error)

    def test_successful_write_is_still_verified_normally(self):
        html = "<p>new</p>"
        verified = JoomlaConnectorArticle(
            article_id=46,
            title="Partners",
            alias="partners",
            body_html=html,
        )

        with patch.object(
            self.adapter,
            "_command",
            return_value={},
        ) as command, patch.object(
            self.adapter,
            "_get_article",
            return_value=verified,
        ):
            article, recovered = self.adapter._write_and_verify(
                self.client,
                "update",
                46,
                html,
                marker_uuid="test",
                expected_hash="a" * 64,
            )

        self.assertFalse(recovered)
        self.assertEqual(article, verified)
        command.assert_called_once()
