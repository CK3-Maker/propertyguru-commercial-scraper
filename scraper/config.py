"""Configuration loader — reads .env and exposes typed settings."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"
DEBUG_DIR = BASE_DIR / "debug"

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

PROPERTYGURU_URL: str = os.getenv(
    "PROPERTYGURU_URL",
    "https://www.propertyguru.com.my/bm/hartanah-dijual"
    "?listingType=sale&page=1&isCommercial=true&tenureCode=M&sort=date&order=desc",
)

IPROPERTY_URL: str = os.getenv(
    "IPROPERTY_URL",
    "https://www.iproperty.com.my/property-for-sale"
    "?listingType=sale&page=1&isCommercial=true&tenureCode=M",
)

SOURCES: list[dict] = [
    {"name": "PropertyGuru", "base_url": PROPERTYGURU_URL, "domain": "propertyguru.com.my"},
    {"name": "iProperty", "base_url": IPROPERTY_URL, "domain": "iproperty.com.my"},
]

MAX_PAGES: int = int(os.getenv("MAX_PAGES", "10"))

PAGE_DELAY_MIN: int = int(os.getenv("PAGE_DELAY_MIN_SECONDS", "2"))
PAGE_DELAY_MAX: int = int(os.getenv("PAGE_DELAY_MAX_SECONDS", "5"))
DETAIL_DELAY_MIN: int = int(os.getenv("DETAIL_DELAY_MIN_SECONDS", "3"))
DETAIL_DELAY_MAX: int = int(os.getenv("DETAIL_DELAY_MAX_SECONDS", "7"))

TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kuala_Lumpur")

SEEN_LISTINGS_PATH = DATA_DIR / "seen_listings.json"

COMMERCIAL_KEYWORDS: list[str] = [
    "freehold", "leasehold", "corner", "semi-d", "detached",
    "factory", "warehouse", "industrial", "commercial land",
    "main road", "high ceiling", "power supply", "loading bay",
    "gated", "guarded", "renovated", "tenanted", "vacant",
    "investment", "below market", "urgent sale", "negotiable",
]
