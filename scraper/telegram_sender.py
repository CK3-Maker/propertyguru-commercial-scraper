"""Send scrape reports to Telegram."""

import logging
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from scraper.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}"


def _api_url(method: str) -> str:
    return f"{API_BASE.format(token=TELEGRAM_BOT_TOKEN)}/{method}"


def is_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def send_message(text: str) -> bool:
    if not is_configured():
        logger.warning("Telegram not configured — skipping message")
        return False

    # Telegram messages max 4096 chars
    if len(text) > 4000:
        text = text[:3997] + "..."

    resp = requests.post(
        _api_url("sendMessage"),
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        logger.error("Telegram sendMessage failed: %s %s", resp.status_code, resp.text)
        resp.raise_for_status()

    logger.info("Telegram message sent")
    return True


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def send_document(filepath: Path, caption: str = "") -> bool:
    if not is_configured():
        logger.warning("Telegram not configured — skipping document")
        return False

    with open(filepath, "rb") as f:
        resp = requests.post(
            _api_url("sendDocument"),
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption[:1024] if caption else "",
            },
            files={"document": (filepath.name, f)},
            timeout=60,
        )
    if resp.status_code != 200:
        logger.error("Telegram sendDocument failed: %s %s", resp.status_code, resp.text)
        resp.raise_for_status()

    logger.info("Telegram document sent: %s", filepath.name)
    return True


def build_summary_message(
    now_str: str,
    window_start: str,
    window_end: str,
    pages_checked: int,
    total_scanned: int,
    new_count: int,
    fail_count: int,
    new_listings: list[dict],
) -> str:
    lines = [
        "<b>Commercial Property New Listings Report</b>",
        f"Date: {now_str}",
        f"Scrape Window: {window_start} to {window_end} MYT",
        f"Sources: PropertyGuru + iProperty",
        "",
        "<b>Summary:</b>",
        f"- Pages checked: {pages_checked}",
        f"- Total listings scanned: {total_scanned}",
        f"- New listings found: {new_count}",
        f"- Detail pages failed: {fail_count}",
        "",
    ]

    if new_listings:
        lines.append("<b>Top new listings:</b>")
        for i, lst in enumerate(new_listings[:5], 1):
            source = lst.get("source", "")
            title = lst.get("detail_title") or lst.get("title", "N/A")
            price = lst.get("price", "N/A")
            location = lst.get("address") or lst.get("location", "N/A")
            url = lst.get("url", "")
            lines.append(f"{i}. [{source}] {title} — {price} — {location}")
            if url:
                lines.append(f"   {url}")
        lines.append("")
        lines.append("Excel report attached.")
    else:
        lines.append("No new commercial listings found for today's 6 PM scrape.")

    return "\n".join(lines)


def send_alert(message: str) -> None:
    try:
        send_message(f"⚠️ <b>Scraper Alert</b>\n\n{message}")
    except Exception as exc:
        logger.error("Failed to send Telegram alert: %s", exc)
