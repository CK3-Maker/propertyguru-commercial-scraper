"""HTTP session using cloudscraper to bypass Cloudflare."""

import logging
import cloudscraper

logger = logging.getLogger(__name__)


def create_scraper() -> cloudscraper.CloudScraper:
    """Create a cloudscraper session that handles Cloudflare challenges."""
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "darwin", "desktop": True},
    )
    scraper.headers.update({
        "Accept-Language": "en-MY,en;q=0.9,ms;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    logger.info("CloudScraper session created")
    return scraper
