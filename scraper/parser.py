"""HTML parsing helpers and data normalization."""

import re
import logging
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup, Tag

from scraper.config import COMMERCIAL_KEYWORDS

logger = logging.getLogger(__name__)

DOMAIN_MAP = {
    "propertyguru": "https://www.propertyguru.com.my",
    "iproperty": "https://www.iproperty.com.my",
}


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(url: str, domain: str = "") -> str:
    if not url:
        return ""
    if url.startswith("/"):
        base = domain or DOMAIN_MAP["propertyguru"]
        url = urljoin(base, url)
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def extract_listing_id(url: str) -> str:
    """Derive a unique listing ID from the URL path.

    PropertyGuru: /senarai-hartanah/something-12345678
    iProperty: /property/area/name/sale-12345678/
    """
    url = normalize_url(url)
    match = re.search(r"[/-](\d{5,})/?$", url)
    if match:
        return match.group(1)
    match = re.search(r"-(\d{5,})(?:/|$)", url)
    if match:
        return match.group(1)
    path = urlparse(url).path.rstrip("/")
    return path.split("/")[-1] if path else url


def parse_price(text: str) -> tuple[str, float | None]:
    """Return (display_price, numeric_value)."""
    text = clean_text(text)
    if not text:
        return ("", None)
    numbers = re.findall(r"[\d,]+\.?\d*", text.replace(",", ""))
    numeric = float(numbers[0]) if numbers else None
    return (text, numeric)


def parse_sqft(text: str) -> tuple[str, float | None]:
    text = clean_text(text)
    if not text:
        return ("", None)
    numbers = re.findall(r"[\d,]+\.?\d*", text.replace(",", ""))
    numeric = float(numbers[0]) if numbers else None
    return (text, numeric)


def extract_keywords(description: str) -> list[str]:
    lower = description.lower()
    return [kw for kw in COMMERCIAL_KEYWORDS if kw in lower]


def first_match_text(soup: BeautifulSoup | Tag, selectors: list[str]) -> str:
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            return clean_text(el.get_text())
    return ""


def first_match_attr(soup: BeautifulSoup | Tag, selectors: list[str], attr: str) -> str:
    for sel in selectors:
        el = soup.select_one(sel)
        if el and el.get(attr):
            return str(el[attr])
    return ""


def first_match_elements(soup: BeautifulSoup | Tag, selectors: list[str]) -> list[Tag]:
    for sel in selectors:
        els = soup.select(sel)
        if els:
            return els
    return []
