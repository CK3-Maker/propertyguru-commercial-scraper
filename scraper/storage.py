"""Persistent storage for seen listings using JSON."""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from scraper.config import SEEN_LISTINGS_PATH

logger = logging.getLogger(__name__)


def load_seen_listings() -> dict:
    """Load the seen-listings database, creating it if missing or corrupt."""
    if not SEEN_LISTINGS_PATH.exists():
        return {"last_run_at": None, "listings": {}}
    try:
        data = json.loads(SEEN_LISTINGS_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "listings" not in data:
            raise ValueError("unexpected schema")
        return data
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Corrupt seen_listings.json — backing up and resetting: %s", exc)
        backup = SEEN_LISTINGS_PATH.with_suffix(".json.bak")
        shutil.copy2(SEEN_LISTINGS_PATH, backup)
        return {"last_run_at": None, "listings": {}}


def save_seen_listings(data: dict) -> None:
    SEEN_LISTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEEN_LISTINGS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.info("Saved %d listings to %s", len(data.get("listings", {})), SEEN_LISTINGS_PATH)


def is_listing_seen(data: dict, listing_id: str) -> bool:
    return listing_id in data.get("listings", {})


def mark_listing_seen(
    data: dict,
    listing_id: str,
    url: str,
    title: str,
    price: str,
    now: datetime,
) -> None:
    listings = data.setdefault("listings", {})
    if listing_id in listings:
        listings[listing_id]["last_seen_at"] = now.isoformat()
    else:
        listings[listing_id] = {
            "listing_id": listing_id,
            "url": url,
            "title": title,
            "price": price,
            "first_seen_at": now.isoformat(),
            "last_seen_at": now.isoformat(),
            "source": "propertyguru",
        }
