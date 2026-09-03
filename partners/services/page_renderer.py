from dataclasses import dataclass
from hashlib import sha256
from html import escape
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from django.conf import settings


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
    value = (placement.url_override or placement.client.domain).strip()
    if value.startswith("//"):
        value = "https:" + value
    elif not urlparse(value).scheme:
        value = f"https://{value.strip('/')}"

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Некорректный URL клиента «{placement.client.name}»: {value}")
    return value


def _public_url(value):
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme or value.startswith("//"):
        return value

    public_base_url = getattr(settings, "PUBLIC_BASE_URL", "").strip()
    if not public_base_url:
        if not settings.DEBUG:
            raise ValueError(
                "PUBLIC_BASE_URL не настроен: JPC не может безопасно передать загруженную картинку "
                "в Joomla как абсолютный URL"
            )
        return value
    return urljoin(public_base_url.rstrip("/") + "/", value.lstrip("/"))


def _image_url(placement):
    if placement.image_override:
        return _public_url(placement.image_override)
    if placement.client.logo:
        return _public_url(placement.client.logo.url)
    return ""


def _link_rel(placement):
    rel = []
    if placement.target_blank:
        rel.append("noopener")
    if placement.nofollow:
        rel.append("nofollow")
    if placement.sponsored:
        rel.append("sponsored")
    return rel


def _link_attributes(placement):
    attrs = []
    if placement.target_blank:
        attrs.append('target="_blank"')
    rel = _link_rel(placement)
    if rel:
        attrs.append(f'rel="{" ".join(rel)}"')
    return (" " + " ".join(attrs)) if attrs else ""


def _apply_link_attributes(link, url, placement):
    link["href"] = url
    link.attrs.pop("target", None)
    link.attrs.pop("rel", None)
    if placement.target_blank:
        link["target"] = "_blank"
    rel = _link_rel(placement)
    if rel:
        link["rel"] = rel


def _text_link_html(url, link_text, placement):
    soup = BeautifulSoup("", "html.parser")
    link = soup.new_tag("a")
    link.string = link_text
    _apply_link_attributes(link, url, placement)
    return str(link)


def _plain_client_html(description, link_text, url, placement):
    description_html = escape(description.strip()).replace("\r\n", "\n").replace("\r", "\n")
    description_html = description_html.replace("\n", "<br>\n")
    separator = " " if description_html else ""
    return description_html + separator + _text_link_html(url, link_text, placement)


def _advanced_client_html(value, link_text, url, placement):
    soup = BeautifulSoup(value, "html.parser")
    links = list(soup.find_all("a"))
    text_link = next((link for link in links if link.find("img") is None), None)

    for link in links:
        if link is not text_link:
            link.unwrap()

    if text_link is None:
        if soup.contents:
            soup.append(" ")
        text_link = soup.new_tag("a")
        text_link.string = link_text
        soup.append(text_link)
    elif not text_link.get_text(strip=True):
        text_link.clear()
        text_link.string = link_text

    _apply_link_attributes(text_link, url, placement)
    return str(soup)


def _client_html(placement, url):
    client = placement.client
    link_text = (
        placement.link_text_override.strip()
        or client.link_text.strip()
        or client.name
    )
    advanced_html = placement.html_override or client.default_html
    if advanced_html:
        return _advanced_client_html(advanced_html, link_text, url, placement)

    description = placement.description_override or client.description
    return _plain_client_html(description, link_text, url, placement)


def _validate_partner_item(item_html, template_name, client_name, expected_url):
    soup = BeautifulSoup(item_html, "html.parser")
    items = soup.find_all("li")
    links = soup.find_all("a")
    image_links = [link for link in links if link.find("img") is not None]
    text_links = [link for link in links if link.find("img") is None]
    nested_link = any(link.find_parent("a") is not None for link in links)

    valid = (
        len(items) == 1
        and len(links) == 2
        and len(image_links) == 1
        and len(text_links) == 1
        and not nested_link
        and all(link.get("href") == expected_url for link in links)
    )
    if not valid:
        raise ValueError(
            f"Шаблон «{template_name}» не может сформировать партнёра «{client_name}»: "
            "каждый <li> должен содержать ровно две ненаслаивающиеся ссылки на URL клиента — "
            "одну вокруг картинки и одну в текстовом описании."
        )


def render_page(donor, placements=None, page_template=None):
    page_template = page_template or donor.template
    if page_template is None:
        raise ValueError("Для донора не выбран шаблон")
    placements = (
        placements
        if placements is not None
        else donor.placements.select_related("client")
        .filter(enabled=True, client__enabled=True)
        .order_by("position", "id")
    )
    rendered_items, clients = [], []
    for placement in placements:
        client = placement.client
        url = _client_url(placement)
        rendered_item = _replace(
            page_template.item_html,
            {
                "url": escape(url, quote=True),
                "link_attributes": _link_attributes(placement),
                "image": escape(_image_url(placement), quote=True),
                "client_name": escape(client.name),
                "client_html": _client_html(placement, url),
            },
        )
        _validate_partner_item(rendered_item, page_template.name, client.name, url)
        rendered_items.append(rendered_item)
        clients.append(client)
    marker = f"<!-- JPC-MANAGED-PAGE:{donor.managed_marker_uuid} -->"
    body = marker + "\n" + _replace(page_template.wrapper_html, {"items": "\n".join(rendered_items)})
    final = (
        f"<style>\n{page_template.css}\n</style>\n\n{body}"
        if page_template.include_css_in_article and page_template.css
        else body
    )
    return RenderedPage(
        body,
        page_template.css,
        final,
        sha256(body.encode()).hexdigest(),
        tuple(clients),
    )


def has_managed_marker(html, donor):
    return f"<!-- JPC-MANAGED-PAGE:{donor.managed_marker_uuid} -->" in html
