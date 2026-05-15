"""Commercial Property Scraper — PropertyGuru + iProperty daily entry point."""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytz

from scraper.config import TIMEZONE, LOGS_DIR, SOURCES
from scraper.browser import create_scraper
from scraper.listing_scraper import scrape_listings
from scraper.detail_scraper import scrape_all_details
from scraper.storage import load_seen_listings, save_seen_listings, mark_listing_seen
from scraper.excel_exporter import export_excel
from scraper.telegram_sender import (
    send_message, send_document, build_summary_message,
    send_alert, is_configured,
)


def setup_logging(now: datetime) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"scraper_{now.strftime('%Y-%m-%d')}.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)


def run() -> int:
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    setup_logging(now)
    logger = logging.getLogger("main")

    source_names = ", ".join(s["name"] for s in SOURCES)
    logger.info("=" * 60)
    logger.info("Commercial Property Scraper starting")
    logger.info("Sources: %s", source_names)
    logger.info("Time: %s", now.isoformat())
    logger.info("=" * 60)

    seen_data = load_seen_listings()
    last_run = seen_data.get("last_run_at")
    if last_run:
        logger.info("Last run: %s", last_run)
    else:
        logger.info("First run — no previous scrape data")

    window_start = (now - timedelta(days=1)).strftime("%Y-%m-%d 18:01")
    window_end = now.strftime("%Y-%m-%d 18:00")
    now_str = now.strftime("%Y-%m-%d")

    session = create_scraper()
    all_new: list[dict] = []
    all_old: list[dict] = []
    all_enriched: list[dict] = []
    total_pages = 0
    total_fail = 0
    blocked_sources: list[str] = []

    for source in SOURCES:
        name = source["name"]
        base_url = source["base_url"]
        domain = source["domain"]
        logger.info("--- Scraping %s ---", name)

        try:
            new_listings, old_listings, pages_checked = scrape_listings(
                session, seen_data,
                base_url=base_url, source_name=name, domain=domain,
            )
            total_pages += pages_checked
            all_old.extend(old_listings)

            logger.info(
                "[%s] Listing scrape done: %d new, %d old across %d pages",
                name, len(new_listings), len(old_listings), pages_checked,
            )

            if new_listings:
                enriched, fail_count = scrape_all_details(session, new_listings, now)
                all_enriched.extend(enriched)
                total_fail += fail_count
            else:
                logger.info("[%s] No new listings — skipping detail scraping", name)

        except RuntimeError as exc:
            if "CAPTCHA" in str(exc) or "bot detection" in str(exc).lower():
                blocked_sources.append(name)
                logger.error("[%s] Blocked: %s", name, exc)
            else:
                logger.exception("[%s] Runtime error", name)
        except Exception:
            logger.exception("[%s] Unexpected error", name)

    if blocked_sources:
        send_alert(
            f"Scraper blocked on: {', '.join(blocked_sources)}\n"
            f"Time: {now.isoformat()}\n"
            "Check debug/ folder for details."
        )
        if not all_enriched and not all_old:
            return 1

    # Update seen listings
    for lst in all_enriched:
        mark_listing_seen(
            seen_data,
            lst["listing_id"],
            lst["url"],
            lst.get("detail_title") or lst.get("title", ""),
            lst.get("price", ""),
            now,
        )
    for lst in all_old:
        mark_listing_seen(
            seen_data,
            lst["listing_id"],
            lst["url"],
            lst.get("title", ""),
            lst.get("price", ""),
            now,
        )
    seen_data["last_run_at"] = now.isoformat()
    save_seen_listings(seen_data)

    # Excel export
    total_scanned = len(all_enriched) + len(all_old)
    summary = {
        "Report Date": now_str,
        "Scrape Window Start": window_start,
        "Scrape Window End": window_end,
        "Sources": source_names,
        "Total Pages Checked": total_pages,
        "Total Listings Found": total_scanned,
        "New Listings Count": len(all_enriched),
        "Old Listings Count": len(all_old),
        "Failed Detail Pages": total_fail,
        "Blocked Sources": ", ".join(blocked_sources) if blocked_sources else "None",
        "Generated At": now.isoformat(),
    }

    excel_path: Path | None = None
    try:
        excel_path = export_excel(all_enriched, summary, now)
        logger.info("Excel exported: %s", excel_path)
    except Exception:
        logger.exception("Excel export failed")

    # Telegram
    msg = build_summary_message(
        now_str, window_start, window_end,
        total_pages, total_scanned,
        len(all_enriched), total_fail,
        all_enriched,
    )

    if is_configured():
        try:
            send_message(msg)
        except Exception:
            logger.exception("Failed to send Telegram summary")

        if excel_path and excel_path.exists():
            try:
                send_document(excel_path, caption=f"Commercial Property Report {now_str}")
            except Exception:
                logger.exception("Failed to send Telegram document")
        elif not excel_path:
            try:
                send_message("Excel report generation failed. Check logs for details.")
            except Exception:
                logger.exception("Failed to send Telegram error notice")
    else:
        logger.warning("Telegram not configured — results only in Excel and logs")

    logger.info("Scraper finished. New: %d, Failed details: %d", len(all_enriched), total_fail)
    return 0


def main() -> None:
    exit_code = run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
