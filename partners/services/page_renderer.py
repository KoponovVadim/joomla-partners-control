from dataclasses import dataclass
from hashlib import sha256
from html import escape
from urllib.parse import urlparse

@dataclass(frozen=True)
class RenderedPage:
    body_html: str
    css: str
    final_html: str
    body_hash: str
    clients: tuple

ALLOWED_TOKENS = {"items", "url", "link_attributes", "image", "client_name", "client_html"}

def _replace(template, values):
    result = template
    for token in ALLOWED_TOKENS:
        result = result.replace("{{ " + token + " }}", str(values.get(token, "")))
        result = result.replace("{{" + token + "}}", str(values.get(token, "")))
    return result

def _client_url(placement):
    value = placement.url_override or placement.client.domain
    return value if urlparse(value).scheme else f"https://{value.strip('/')}"

def _image_url(placement):
    if placement.image_override: return placement.image_override
    if placement.client.logo: return placement.client.logo.url
    return ""

def render_page(donor, placements=None, page_template=None):
    page_template = page_template or donor.template
    if page_template is None:
        raise ValueError("Для донора не выбран шаблон")
    placements = placements if placements is not None else donor.placements.select_related("client").filter(enabled=True, client__enabled=True).order_by("position", "id")
    rendered_items, clients = [], []
    for placement in placements:
        client = placement.client
        attrs = []
        rel = []
        if placement.target_blank:
            attrs.append('target="_blank"')
            rel.append("noopener")
        if placement.nofollow: rel.append("nofollow")
        if placement.sponsored: rel.append("sponsored")
        if rel: attrs.append(f'rel="{" ".join(rel)}"')
        attr_text = (" " + " ".join(attrs)) if attrs else ""
        rendered_items.append(_replace(page_template.item_html, {
            "url": escape(_client_url(placement), quote=True), "link_attributes": attr_text,
            "image": escape(_image_url(placement), quote=True), "client_name": escape(client.name),
            "client_html": placement.html_override or client.default_html,
        }))
        clients.append(client)
    marker = f"<!-- JPC-MANAGED-PAGE:{donor.managed_marker_uuid} -->"
    body = marker + "\n" + _replace(page_template.wrapper_html, {"items": "\n".join(rendered_items)})
    final = f"<style>\n{page_template.css}\n</style>\n\n{body}" if page_template.include_css_in_article and page_template.css else body
    return RenderedPage(body, page_template.css, final, sha256(body.encode()).hexdigest(), tuple(clients))

def has_managed_marker(html, donor):
    return f"<!-- JPC-MANAGED-PAGE:{donor.managed_marker_uuid} -->" in html
