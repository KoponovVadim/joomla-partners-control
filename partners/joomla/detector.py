import httpx
from bs4 import BeautifulSoup

def detect_version(admin_url, timeout=8):
    try:
        response = httpx.get(admin_url, follow_redirects=True, timeout=timeout)
        text = response.text.lower()
        soup = BeautifulSoup(response.text, "html.parser")
        generator = soup.find("meta", attrs={"name": "generator"})
        signature = (generator.get("content", "") if generator else "").lower() + text
        for version in ("5", "4", "3"):
            if f"joomla! {version}" in signature or f"joomla {version}" in signature:
                return version
    except httpx.HTTPError:
        pass
    return "unknown"

