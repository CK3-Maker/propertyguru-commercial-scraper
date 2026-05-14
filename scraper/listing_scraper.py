"""Scrape listing cards from search result pages."""

import logging
import random
import re
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from bs4 import BeautifulSoup
import cloudscraper

from scraper.config import (
    BASE_URL, MAX_PAGES,
    PAGE_DELAY_MIN, PAGE_DELAY_MAX, DEBUG_DIR,
)
from scraper.parser import (
    clean_text, normalize_url, extract_listing_id, parse_price,
)
from scraper.storage import is_listing_seen

logger = logging.getLogger(__name__)


def build_page_url(page_num: int) -> str:
    parsed = urlparse(BASE_URL)
    qs = parse_qs(parsed.query)
    qs["page"] = [str(page_num)]
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _detect_block(html: str) -> bool:
    lower = html.lower()
    signals = ["captcha", "are you a robot", "verify you are human", "access denied"]
    return any(s in lower for s in signals)


def _save_debug_html(html: str, label: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    path = DEBUG_DIR / f"{label}_{ts}.html"
    path.write_text(html, encoding="utf-8")
    logger.info("Debug HTML saved: %s", path)


def _parse_listing_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.listing-card-v2")

    if not cards:
        logger.warning("No listing cards found")
        return []

    results: list[dict] = []
    for card in cards:
        # URL and title
        title_el = card.select_one("h3.listing-type-text")
        link_els = card.select('a[href*="senarai-hartanah"], a[href*="property-for-sale"]')
        href = link_els[0]["href"] if link_els else ""
        url = normalize_url(href)
        listing_id = extract_listing_id(url)
        title = clean_text(title_el.get_text()) if title_el else ""

        # Price — prefer the .amount child to avoid "Boleh dirunding" etc.
        price_amount = card.select_one(".listing-price .amount, .listing-price h2")
        if not price_amount:
            price_amount = card.select_one(".listing-price")
        price_display, price_numeric = parse_price(
            clean_text(price_amount.get_text()) if price_amount else ""
        )

        # PSF
        psf_el = card.select_one(".listing-ppa")
        psf = clean_text(psf_el.get_text()) if psf_el else ""

        # Address / location
        addr_el = card.select_one(".listing-address")
        location = clean_text(addr_el.get_text()) if addr_el else ""

        # Features (property type, size, tenure etc.)
        feature_els = card.select(".listing-feature-group p.pg-font-body-xs")
        feat_texts = [clean_text(f.get_text()) for f in feature_els]

        property_type = ""
        built_up = ""
        land_size = ""
        tenure = ""
        for ft in feat_texts:
            ft_lower = ft.lower()
            # Skip pure numbers (room/facility counts)
            if re.match(r"^\d+$", ft.strip()):
                continue
            if any(k in ft_lower for k in ["kps", "sq", "ekar", "acre", "hektar"]):
                if not land_size:
                    land_size = ft
                else:
                    built_up = ft
            elif any(k in ft_lower for k in ["rizab", "freehold", "leasehold", "pegangan"]):
                tenure = ft
            elif any(k in ft_lower for k in [
                "tanah", "kilang", "gudang", "kedai", "pejabat", "hotel",
                "resort", "hartanah", "komersial", "perindustrian", "pertanian",
            ]):
                if not property_type:
                    property_type = ft

        # Agent
        agent_el = card.select_one(".contact-details__title")
        agent_name = clean_text(agent_el.get_text()) if agent_el else ""

        # Posted date
        posted_el = card.select_one(".pg-font-caption-xs")
        posted_date_text = clean_text(posted_el.get_text()) if posted_el else ""

        # Badge labels
        badge_els = card.select(".listing-card-v2__badges-row span")
        listing_label = ", ".join(clean_text(b.get_text()) for b in badge_els if clean_text(b.get_text()))

        if not url:
            continue

        results.append({
            "listing_id": listing_id,
            "title": title,
            "url": url,
            "price": price_display,
            "price_numeric": price_numeric,
            "location": location,
            "property_type": property_type,
            "built_up": built_up,
            "land_size": land_size,
            "tenure": tenure,
            "psf": psf,
            "agent_name": agent_name,
            "agency_name": "",
            "posted_date_text": posted_date_text,
            "listing_label": listing_label,
        })

    return results


def scrape_listings(
    session: cloudscraper.CloudScraper,
    seen_data: dict,
) -> tuple[list[dict], list[dict], int]:
    """Scrape listing pages. Returns (new_listings, old_listings, pages_checked)."""
    new_listings: list[dict] = []
    old_listings: list[dict] = []
    pages_checked = 0

    for page_num in range(1, MAX_PAGES + 1):
        url = build_page_url(page_num)
        logger.info("Scraping page %d: %s", page_num, url)

        try:
            resp = session.get(url, timeout=30)
        except Exception as exc:
            logger.error("Failed to load page %d: %s", page_num, exc)
            break

        pages_checked += 1

        if resp.status_code != 200:
            logger.error("Page %d returned status %d", page_num, resp.status_code)
            _save_debug_html(resp.text, f"error_p{page_num}")
            break

        html = resp.text

        if _detect_block(html):
            logger.error("Bot detection on page %d — stopping", page_num)
            _save_debug_html(html, f"blocked_p{page_num}")
            raise RuntimeError("CAPTCHA or bot detection triggered")

        cards = _parse_listing_cards(html)
        logger.info("Page %d: found %d listing cards", page_num, len(cards))

        if not cards:
            logger.info("No cards on page %d — stopping pagination", page_num)
            if pages_checked == 1:
                _save_debug_html(html, "no_cards_p1")
            break

        page_new_count = 0
        for card in cards:
            if is_listing_seen(seen_data, card["listing_id"]):
                old_listings.append(card)
            else:
                new_listings.append(card)
                page_new_count += 1

        logger.info(
            "Page %d: %d new, %d already seen",
            page_num, page_new_count, len(cards) - page_new_count,
        )

        if page_new_count == 0:
            logger.info("Full page of old listings — stopping pagination")
            break

        if page_num < MAX_PAGES:
            delay = random.uniform(PAGE_DELAY_MIN, PAGE_DELAY_MAX)
            logger.debug("Waiting %.1fs before next page", delay)
            time.sleep(delay)

    return new_listings, old_listings, pages_checked
