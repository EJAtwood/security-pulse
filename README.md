# 🛡️ Security Pulse

A daily security & AI intelligence digest. Security Pulse aggregates the CISA Known Exploited Vulnerabilities (KEV) catalog plus a curated set of security and AI-news RSS/Atom feeds, then delivers a clean, card-based **HTML email** to your inbox every morning — fully automated via GitHub Actions.

## Features

- ✅ **Card-based HTML email digest** — a polished, mobile-friendly email with section headers, clickable article titles, summaries, and per-item accent bars (plain-text fallback included)
- ✅ **CISA KEV section** — the Known Exploited Vulnerabilities catalog as a top-priority section with `EXPLOITED` / `RANSOMWARE` badges, CVE links to NVD, date added, and remediation due dates
- ✅ **Grouped sections** — feeds are organized into **Vulnerabilities & Threats** and **AI News & Model Releases**
- ✅ **Bot-block-resistant fetching** — sends full browser headers so sources behind Akamai (e.g. CISA) don't return `403`/empty feeds
- ✅ **Markdown archive** — also writes `SECURITY_FEED.md` to the repo as a committed daily record
- ✅ **Automated daily** — GitHub Actions runs on a schedule with no servers to manage (free-tier friendly)
- ✅ **Easy to configure** — YAML-based feed, section, and delivery configuration

## Data Sources

**Vulnerabilities & Threats**
- **CISA KEV catalog** (`known_exploited_vulnerabilities.json`) — actively exploited vulnerabilities
- **CISA Advisories** (RSS)
- **The Hacker News**
- **Wiz Security Blog**
- **Dark Reading**

**AI News & Model Releases**
- **TechCrunch AI**
- **The Verge AI**
- **Simon Willison** (LLM / model-release analysis)

All sources are defined in `config.yaml` and can be toggled, added, or removed freely.

## Quick Start

### Prerequisites
- Python 3.8+ (CI uses 3.11)
- Git, and a GitHub account for automated delivery

### Local Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/EJAtwood/security-pulse.git
   cd security-pulse
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run locally**
   ```bash
   python pulse.py
   ```
   Feeds are fetched and `SECURITY_FEED.md` is generated. Email delivery is skipped automatically unless SMTP settings are configured (see below), so this is safe to run locally.

5. **Check the output**
   ```bash
   cat SECURITY_FEED.md
   ```

## Configuration

Everything is controlled by `config.yaml`.

### Feeds
Each feed has a `category` (`security` or `ai`) that determines which section it appears in:

```yaml
feeds:
  my_custom_feed:
    name: "Custom Security Source"
    url: "https://example.com/feed.xml"
    category: security   # or: ai
    enabled: true
```

### CISA KEV
```yaml
kev:
  enabled: true
  url: "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
  max_entries: 8         # most recently added entries to show
```

### Sections
Controls section titles, emoji, and display order:

```yaml
sections:
  - key: security
    title: "Vulnerabilities & Threats"
    emoji: "🛡️"
  - key: ai
    title: "AI News & Model Releases"
    emoji: "🤖"
```

### Output & fetch
```yaml
output:
  file: "SECURITY_FEED.md"
  max_entries_per_feed: 5
  summary_length: 220

fetch:
  timeout: 20
  user_agent: "Mozilla/5.0 ..."   # browser UA used for all requests
```

## GitHub Setup

### 1. Email delivery secrets

Daily email is delivered over SMTP. Add these repository secrets
(**Settings → Secrets and variables → Actions**):

| Secret | Description |
| --- | --- |
| `EMAIL_SMTP_SERVER` | SMTP host (e.g. `smtp-relay.brevo.com`) |
| `EMAIL_SMTP_PORT` | SMTP port (e.g. `587`) |
| `EMAIL_USERNAME` | SMTP username |
| `EMAIL_PASSWORD` | SMTP password / API key |
| `EMAIL_FROM` | Sender address |
| `EMAIL_TO` | Recipient(s), comma-separated |

These environment variables override the placeholder values in `config.yaml`, so no real credentials live in the repo. Email is enabled via `email.enabled: true` in `config.yaml`.

### 2. Enable GitHub Actions

1. Go to the **Actions** tab and enable workflows if prompted.
2. Ensure **Settings → Actions → General → Workflow permissions** is set to **Read and write** (the workflow commits `SECURITY_FEED.md`).

### 3. Run it

- **Automatically:** the workflow runs daily at **12:00 UTC**.
- **Manually:** **Actions → Daily Security Pulse → Run workflow**, or:
  ```bash
  gh workflow run daily_pulse.yml --repo EJAtwood/security-pulse
  ```

## Project Structure

```
security-pulse/
├── .github/
│   └── workflows/
│       └── daily_pulse.yml    # GitHub Actions workflow (cron + manual)
├── pulse.py                   # Main script: fetch, render Markdown + HTML, email
├── config.yaml                # Feeds, KEV, sections, output & email config
├── requirements.txt           # Python dependencies
├── SECURITY_FEED.md           # Generated daily digest (committed by the workflow)
├── README.md                  # This file
├── CONTRIBUTING.md            # Contribution guidelines
├── LICENSE                    # MIT License
└── .gitignore
```

## How It Works

```
1. Schedule (daily 12:00 UTC) or manual dispatch
   ↓
2. GitHub Actions runs pulse.py
   ↓
3. Fetch CISA KEV catalog + all enabled RSS/Atom feeds (browser headers)
   ↓
4. Clean, sort, and group entries into sections
   ↓
5. Render a Markdown archive (SECURITY_FEED.md) and a card-based HTML email
   ↓
6. Send the HTML email via SMTP, then commit & push SECURITY_FEED.md
```

## Roadmap

- [x] Email digest delivery
- [x] CISA KEV integration with severity/ransomware badges
- [x] AI news & model-release section
- [ ] Custom filtering by keywords
- [ ] Slack/Discord webhook integration
- [ ] Web dashboard to view feeds
- [ ] Database storage of articles

## Troubleshooting

### ❌ A feed shows no entries
- Some sources (notably CISA) block non-browser clients. `pulse.py` already sends full browser headers; if a new feed still returns nothing, verify the URL in a browser and check the workflow logs.
- Note: `Accept-Encoding` intentionally excludes `br` (brotli), since `requests` can't decode it without the extra package — leaving it in can produce empty feeds.

### ❌ No email arrives
- Confirm all six `EMAIL_*` secrets are set and `email.enabled: true` in `config.yaml`.
- Check the **Run Pulse Script** step logs — email is skipped with a warning if SMTP config is incomplete.

### ❌ Workflow fails with "permission denied"
- Set **Settings → Actions → General → Workflow permissions** to **Read and write**.

## Resources

- [CISA Known Exploited Vulnerabilities Catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
- [GitHub Actions Documentation](https://docs.github.com/actions)
- [feedparser Documentation](https://feedparser.readthedocs.io/)

## License

MIT License — see [LICENSE](LICENSE) for details.

---

**Built with ❤️ for the security community**
