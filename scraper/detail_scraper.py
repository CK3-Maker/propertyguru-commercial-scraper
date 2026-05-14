"""Scrape individual listing detail pages for full property info."""

import logging
import random
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup
import cloudscraper

from scraper.config import DETAIL_DELAY_MIN, DETAIL_DELAY_MAX
from scraper.parser import clean_text, extract_keywords

logger = logging.getLogger(__name__)


def _try_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            return clean_text(el.get_text())
    return ""


def _try_attr(soup: BeautifulSoup, selectors: list[str], attr: str) -> str:
    for sel in selectors:
        el = soup.select_one(sel)
        if el and el.get(attr):
            return str(el[attr])
    return ""


def _extract_detail_facts(soup: BeautifulSoup) -> list[str]:
    """Extract all individual fact strings from the detail table.

    The detail section has rows with 2 cells each, but each cell is an
    independent fact (not key-value pairs).
    """
    facts: list[str] = []
    for tr in soup.select(".details-section tr, .details-wrapper tr"):
        for td in tr.find_all("td"):
            text = clean_text(td.get_text())
            if text:
                facts.append(text)
    return facts


def _parse_facts(facts: list[str]) -> dict[str, str]:
    """Map raw fact strings to structured fields."""
    result: dict[str, str] = {}

    for fact in facts:
        fl = fact.lower()

        # Property type
        type_keywords = [
            "tanah pertanian", "tanah komersial", "tanah perindustrian",
            "hotel", "resort", "kilang", "gudang", "kedai", "pejabat",
            "hartanah yang lain", "untuk dijual",
        ]
        if any(k in fl for k in type_keywords) and "property_type" not in result:
            result["property_type"] = fact.split(" untuk dijual")[0].strip()

        # Tenure
        tenure_keywords = ["rizab melayu", "freehold", "leasehold", "pegangan bebas", "pajakan"]
        if any(k in fl for k in tenure_keywords) and "tenure" not in result:
            result["tenure"] = fact

        # Furnishing
        furnish_keywords = ["dipasang", "furnished", "unfurnished", "sebahagian"]
        if any(k in fl for k in furnish_keywords) and "furnishing" not in result:
            result["furnishing"] = fact

        # Land area
        if ("luas tanah" in fl or "luas pelan lantai" in fl) and "land_area" not in result:
            result["land_area"] = fact

        # PSF
        if "psf" in fl and "psf_detail" not in result:
            result["psf_detail"] = fact

        # Listing ID
        id_match = re.search(r"(?:ID penyenaraian|Listing ID)\s*-\s*(\d+)", fact, re.IGNORECASE)
        if id_match:
            result["listing_id_page"] = id_match.group(1)

        # Posted date
        date_match = re.match(r"(?:Disenaraikan pada|Listed on)\s+(.+)", fact, re.IGNORECASE)
        if date_match:
            result["posted_date"] = date_match.group(1).strip()

        # Completed year
        if re.match(r"(?:Disiapkan pada|Completed in)\s+\d{4}", fact, re.IGNORECASE):
            result["completed_year"] = fact

    return result


def scrape_detail(
    session: cloudscraper.CloudScraper,
    listing: dict,
    now: datetime,
) -> dict:
    """Scrape a single listing detail page. Returns enriched listing dict."""
    url = listing["url"]
    detail: dict = {**listing, "detail_scraped": False, "detail_error": ""}

    try:
        resp = session.get(url, timeout=30)
    except Exception as exc:
        logger.error("Failed to load detail page %s: %s", url, exc)
        detail["detail_error"] = str(exc)
        return detail

    if resp.status_code != 200:
        logger.warning("Detail page %s returned status %d", url, resp.status_code)
        detail["detail_error"] = f"HTTP {resp.status_code}"
        return detail

    html = resp.text
    if any(s in html.lower() for s in ["captcha", "are you a robot", "access denied"]):
        logger.error("Bot detection on detail page %s", url)
        detail["detail_error"] = "Bot detection"
        return detail

    soup = BeautifulSoup(html, "lxml")

    # Title
    h1 = soup.select_one("h1")
    detail["detail_title"] = clean_text(h1.get_text()) if h1 else listing.get("title", "")

    # Price — separate amount from price type (e.g. "Boleh dirunding")
    price_amount = soup.select_one(".amount, h2.amount")
    price_type = soup.select_one(".price-type, span.price-type")
    if price_amount:
        detail["price"] = clean_text(price_amount.get_text())
    if price_type:
        detail["price_note"] = clean_text(price_type.get_text())

    # Address
    addr_el = soup.select_one(".listing-address, [class*=address]")
    detail["address"] = clean_text(addr_el.get_text()) if addr_el else ""

    # Extract all facts from detail table
    facts = _extract_detail_facts(soup)
    parsed = _parse_facts(facts)
    detail.update(parsed)

    # Description — use description-block-root, not listing-markdown-container
    desc_el = (
        soup.select_one(".description-block-root")
        or soup.select_one(".about-section")
        or soup.select_one("[class*=description]")
    )
    if desc_el:
        # Skip the "Tentang hartanah ini" header
        header = desc_el.select_one("h2, h3")
        if header:
            header.decompose()
        description = clean_text(desc_el.get_text())
    else:
        description = ""
    detail["description"] = description
    detail["commercial_keywords"] = extract_keywords(
        description + " " + detail.get("detail_title", "") + " " + " ".join(facts)
    )

    # Agent info
    agent_el = soup.select_one(".agent-name")
    detail["agent_name_detail"] = clean_text(agent_el.get_text()) if agent_el else ""

    agency_el = soup.select_one(".agency")
    detail["agency_name_detail"] = clean_text(agency_el.get_text()) if agency_el else ""

    agent_link = soup.select_one("a[href*='/ejen-hartanah/'], a[href*='/agent/']")
    detail["agent_profile_url"] = agent_link["href"] if agent_link else ""

    # Photos
    gallery_imgs = soup.select("[class*=gallery] img, [class*=slider] img, [class*=carousel] img")
    detail["photo_count"] = len(gallery_imgs) if gallery_imgs else 0

    og_img = soup.select_one('meta[property="og:image"]')
    detail["main_image_url"] = og_img.get("content", "") if og_img else ""

    # State — extract from address (last part is usually the state)
    address = detail.get("address", "")
    if address:
        parts = [p.strip() for p in address.split(",")]
        if parts:
            detail["state"] = parts[-1]

    detail["detail_scraped"] = True
    detail["scraped_at"] = now.isoformat()
    detail["first_seen_at"] = now.isoformat()

    logger.info("Detail scraped: %s", detail.get("detail_title") or listing.get("title"))
    return detail


def scrape_all_details(
    session: cloudscraper.CloudScraper,
    new_listings: list[dict],
    now: datetime,
) -> tuple[list[dict], int]:
    """Scrape details for all new listings. Returns (enriched_listings, fail_count)."""
    enriched: list[dict] = []
    fail_count = 0

    for i, listing in enumerate(new_listings, 1):
        logger.info("Scraping detail %d/%d: %s", i, len(new_listings), listing["url"])
        detail = scrape_detail(session, listing, now)
        enriched.append(detail)
        if not detail.get("detail_scraped"):
            fail_count += 1

        if i < len(new_listings):
            delay = random.uniform(DETAIL_DELAY_MIN, DETAIL_DELAY_MAX)
            logger.debug("Waiting %.1fs before next detail", delay)
            time.sleep(delay)

    return enriched, fail_count
