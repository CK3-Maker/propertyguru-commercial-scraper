# PropertyGuru Commercial Property Scraper

Automated daily scraper for new commercial property sale listings on PropertyGuru Malaysia. Identifies new listings by comparing against a persistent database, scrapes full details from each listing page, exports to Excel, and sends a Telegram notification with the report.

## What It Does

1. Opens PropertyGuru commercial property sale listings (sorted newest first).
2. Scrapes listing cards across multiple pages.
3. Compares each listing against `data/seen_listings.json` to identify new ones.
4. For every new listing, visits the detail page and extracts comprehensive property info.
5. Generates a formatted Excel report with Summary, New Listings, and Raw Data sheets.
6. Sends a Telegram message with a text summary + the Excel file attached.
7. Updates the seen-listings database for the next run.

## How New Listings Are Identified

The scraper maintains `data/seen_listings.json` — a JSON file mapping listing IDs to metadata. Each listing's unique ID is derived from its URL. A listing is "new" if its ID has never appeared in a previous scrape. Pagination stops when an entire page contains only previously-seen listings, or when the max page limit is reached.

## Setup

### Prerequisites

- Python 3.10+
- A Telegram bot (for notifications)

### Create a Telegram Bot

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot` and follow the prompts.
3. Copy the **bot token** (looks like `123456:ABCdefGHIjklMNO`).
4. Send a message to your new bot, then visit:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
5. Find your **chat_id** in the JSON response under `result[0].message.chat.id`.

### Local Setup

```bash
# Clone the repo
git clone <your-repo-url>
cd propertyguru-commercial-scraper

# Create virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium

# Configure environment
cp .env.example .env
# Edit .env and fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID

# Run
python main.py
```

### Configuration (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot API token |
| `TELEGRAM_CHAT_ID` | — | Telegram chat/group ID |
| `BASE_URL` | PropertyGuru commercial URL | Search URL to scrape |
| `MAX_PAGES` | `10` | Maximum search pages to scrape |
| `HEADLESS` | `true` | Run browser in headless mode |
| `PAGE_DELAY_MIN_SECONDS` | `2` | Min delay between search pages |
| `PAGE_DELAY_MAX_SECONDS` | `5` | Max delay between search pages |
| `DETAIL_DELAY_MIN_SECONDS` | `3` | Min delay between detail pages |
| `DETAIL_DELAY_MAX_SECONDS` | `7` | Max delay between detail pages |
| `TIMEZONE` | `Asia/Kuala_Lumpur` | Timezone for timestamps |

## GitHub Actions Deployment

### 1. Push Code to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

### 2. Add GitHub Secrets

Go to **Settings > Secrets and variables > Actions** and add:

| Secret | Value |
|--------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token |
| `TELEGRAM_CHAT_ID` | Your chat ID |

### 3. Enable Actions

GitHub Actions runs automatically. The workflow is at `.github/workflows/daily-scrape.yml`.

### Schedule

- **Automatic**: Every day at 10:00 UTC (18:00 MYT).
- **Manual**: Go to **Actions > Daily PropertyGuru Scrape > Run workflow**.

The workflow commits the updated `seen_listings.json` back to the repo after each run to persist state across runs.

### Artifacts

Each run uploads the Excel report as a GitHub Actions artifact (retained for 30 days).

## Manual Trigger

```bash
# Via GitHub CLI
gh workflow run daily-scrape.yml

# Or via the GitHub Actions web UI
```

## Troubleshooting

### Telegram not sending

- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are correct.
- Make sure you've sent at least one message to the bot first.
- Check that the bot hasn't been blocked or deleted.

### Playwright browser missing

```bash
playwright install chromium
# On Linux servers, you may also need:
playwright install-deps chromium
```

### PropertyGuru blocking requests

- The scraper uses random delays and realistic headers to be polite.
- If blocked, check `debug/` for HTML and screenshot captures.
- Increase delay values in `.env`.
- The scraper will send a Telegram alert if CAPTCHA is detected.

### No new listings detected

- On first run, all listings are new.
- On subsequent runs, if all listings were seen before, the report says "no new listings."
- To reset, delete or clear `data/seen_listings.json`.

### GitHub Actions timezone

- The cron `0 10 * * *` = 10:00 UTC = 18:00 Malaysia time (MYT, UTC+8).
- GitHub Actions cron can have up to 15 minutes delay.

## Upgrading Storage

The default `seen_listings.json` works well locally and on GitHub Actions (committed back to repo). For more robust persistence:

- **Supabase**: Replace `storage.py` with Supabase client calls to a `seen_listings` table.
- **Google Sheets**: Use `gspread` to read/write a spreadsheet as the database.
- **PostgreSQL**: Use `psycopg2` or `asyncpg` with a hosted database.
- **S3 / Cloud Storage**: Upload/download the JSON file from a bucket.
- **Firebase**: Use `firebase-admin` SDK for Firestore.

## Ethical Scraping

- This scraper uses polite delays between requests.
- It does **not** bypass CAPTCHAs, login walls, or anti-bot protections.
- It runs once daily — low request frequency.
- Use responsibly and respect PropertyGuru's terms of service.
- If the website blocks the scraper, it stops gracefully and notifies you.

## Project Structure

```
propertyguru-commercial-scraper/
├── main.py                          # Entry point
├── scraper/
│   ├── config.py                    # Settings and selectors
│   ├── browser.py                   # Playwright browser manager
│   ├── listing_scraper.py           # Search page scraper
│   ├── detail_scraper.py            # Detail page scraper
│   ├── parser.py                    # HTML parsing & normalization
│   ├── storage.py                   # JSON persistence
│   ├── excel_exporter.py            # Excel report generator
│   └── telegram_sender.py           # Telegram bot integration
├── data/seen_listings.json          # Persistent listing database
├── reports/                         # Generated Excel reports
├── logs/                            # Daily log files
├── debug/                           # HTML/screenshot captures on error
├── .env.example                     # Environment template
├── requirements.txt                 # Python dependencies
└── .github/workflows/daily-scrape.yml  # GitHub Actions workflow
```
