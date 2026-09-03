import re

from .api import JoomlaApiAdapter, JoomlaApiArticle


_UUID_PATTERN = (
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_COMMENT_MARKER_RE = re.compile(
    rf"<!--\s*JPC-MANAGED-PAGE:({_UUID_PATTERN})\s*-->",
    re.IGNORECASE,
)
_SPAN_MARKER_RE = re.compile(
    rf"<span\b(?=[^>]*\bid\s*=\s*['\"]jpc-managed-page-"
    rf"({_UUID_PATTERN})['\"])[^>]*>\s*</span>",
    re.IGNORECASE,
)


class JoomlaFilteredMarkerApiAdapter(JoomlaApiAdapter):
    """Joomla Web Services adapter with a filter-safe managed marker.

    Joomla's API HTML filtering may remove HTML comments from article text.
    JPC keeps comments as its canonical internal representation, but stores the
    marker in Joomla 5 as an empty hidden span with a unique id. The span is
    converted back to the canonical comment immediately after every API read,
    so the rest of JPC does not need Joomla-version-specific marker logic.
    """

    @staticmethod
    def _marker_for_api(match):
        return f'<span id="jpc-managed-page-{match.group(1).lower()}" hidden></span>'

    @staticmethod
    def _marker_for_jpc(match):
        return f"<!-- JPC-MANAGED-PAGE:{match.group(1).lower()} -->"

    @classmethod
    def _html_for_api(cls, html):
        return _COMMENT_MARKER_RE.sub(cls._marker_for_api, str(html or ""))

    @classmethod
    def _html_for_jpc(cls, html):
        return _SPAN_MARKER_RE.sub(cls._marker_for_jpc, str(html or ""))

    def _request(self, client, method, path, **kwargs):
        payload = kwargs.get("json")
        if (
            method.upper() in {"POST", "PATCH"}
            and path.lstrip("/").startswith("content/articles")
            and isinstance(payload, dict)
        ):
            payload = dict(payload)
            for field in ("articletext", "introtext", "fulltext"):
                if isinstance(payload.get(field), str):
                    payload[field] = self._html_for_api(payload[field])
            kwargs["json"] = payload
        return super()._request(client, method, path, **kwargs)

    @classmethod
    def _article_from_resource(cls, resource):
        article = super()._article_from_resource(resource)

        # Joomla 5 Web Services returns the actual article body in `text`.
        # `articletext`/`introtext`/`fulltext` may be absent entirely, so the
        # generic API parser can otherwise see an empty body and falsely report
        # that the managed marker disappeared even though Joomla stored it.
        attributes = resource.get("attributes") if isinstance(resource, dict) else None
        api_text = attributes.get("text") if isinstance(attributes, dict) else None
        body_html = api_text if isinstance(api_text, str) else article.body_html

        return JoomlaApiArticle(
            article_id=article.article_id,
            title=article.title,
            alias=article.alias,
            body_html=cls._html_for_jpc(body_html),
        )
