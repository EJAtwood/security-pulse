# 🛡️ Security Pulse

A lightweight RSS feed aggregator that delivers the latest vulnerability and AI-related security news to your inbox, updated daily via GitHub Actions.

## Features

- ✅ **Automated Daily Updates** - GitHub Actions runs every day to fetch fresh security content
- ✅ **Multi-Source Aggregation** - Pulls from CISA, HackerNews, Wiz, and other security sources
- ✅ **Markdown Output** - Clean, readable markdown file in your repo
- ✅ **Easy to Configure** - YAML-based feed configuration
- ✅ **No External Dependencies** - Runs entirely on GitHub Actions (free tier friendly)
- ✅ **Learning Project** - Perfect for understanding CI/CD, RSS feeds, and automation

## Quick Start

### Prerequisites
- Python 3.8+
- A GitHub account
- Git

### Local Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/security-pulse.git
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

5. **Check the output**
   ```bash
   cat SECURITY_FEED.md
   ```

## Configuration

Edit `config.yaml` to customize:

- **Add/remove feeds** - Add new security RSS feeds
- **Toggle feeds** - Set `enabled: true/false` to include/exclude sources
- **Adjust output** - Change max entries per feed, sorting options
- **Timeout settings** - Configure fetch timeouts and retries

Example:
```yaml
feeds:
  my_custom_feed:
    name: "Custom Security Source"
    url: "https://example.com/feed.xml"
    enabled: true
```

## GitHub Setup

### 1. Create a GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. Repository name: `security-pulse`
3. Description: "Daily security vulnerability & AI risk feed aggregator"
4. Choose: **Public** (for learning & community)
5. Initialize with README: **No** (we have our own)
6. Click **Create repository**

### 2. Add Email Secrets for GitHub Actions (optional)

If you want daily email delivery, add these repository secrets:

- `EMAIL_SMTP_SERVER`
- `EMAIL_SMTP_PORT`
- `EMAIL_USERNAME`
- `EMAIL_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_TO`

Then enable email in `config.yaml` by setting `email.enabled: true` and updating `email.to`.

### 3. Push Your Code

```bash
cd security-pulse
git remote add origin https://github.com/yourusername/security-pulse.git
git branch -M main
git add .
git commit -m "Initial commit: Security Pulse automation setup"
git push -u origin main
```

### 3. Enable GitHub Actions

1. Go to your repository on GitHub
2. Click **Actions** tab
3. GitHub should auto-detect the workflow in `.github/workflows/`
4. Click **I understand my workflows, go ahead and enable them**

### 4. Test the Workflow

1. In the **Actions** tab, click the **Daily Security Pulse** workflow
2. Click **Run workflow** → **Run workflow** (green button)
3. Watch it execute! ✅

Within seconds you should see `SECURITY_FEED.md` appear in your repo.

## Project Structure

```
security-pulse/
├── .github/
│   └── workflows/
│       └── daily_pulse.yml       # GitHub Actions workflow
├── pulse.py                       # Main script
├── config.yaml                    # Feed configuration
├── requirements.txt               # Python dependencies
├── SECURITY_FEED.md              # Generated daily feed (created by script)
├── README.md                      # This file
├── CONTRIBUTING.md               # Contribution guidelines
├── LICENSE                        # MIT License
└── .gitignore                    # Git ignore rules
```

## How It Works

```
1. Schedule (Daily at 12:00 UTC)
   ↓
2. GitHub Actions Runs
   ↓
3. Python Script Fetches All Configured RSS Feeds
   ↓
4. Parses & Formats Latest Entries
   ↓
5. Generates SECURITY_FEED.md
   ↓
6. Git Commits & Pushes to Repository
```

## Roadmap

- [ ] Web dashboard to view feeds
- [ ] Slack/Discord webhook integration
- [ ] Custom filtering by keywords
- [ ] Email digest delivery
- [ ] Database storage of articles
- [ ] Community feed submissions
- [ ] Mobile app support

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to suggest new feeds, report issues, or contribute code.

## Troubleshooting

### ❌ Workflow fails with "permission denied"
Make sure your GitHub Actions has write permissions:
- Go to Settings → Actions → General
- Under "Workflow permissions", select "Read and write permissions"

### ❌ No `SECURITY_FEED.md` is created
- Check the workflow logs in the Actions tab
- Verify all feed URLs are accessible
- Try running `python pulse.py` locally first

### ❌ Feeds are not updating
- Verify the RSS feed URLs are still valid
- Check `config.yaml` to ensure feeds are `enabled: true`
- GitHub Actions runs on UTC time - check the scheduled time

## Resources for Learning

- [GitHub Actions Documentation](https://docs.github.com/actions)
- [RSS Feed Spec](https://www.rssboard.org/rss-specification)
- [feedparser Documentation](https://feedparser.readthedocs.io/)
- [CISA Cyber Advisories](https://www.cisa.gov/news-events/cybersecurity-advisories)

## License

MIT License - see [LICENSE](LICENSE) for details

## Questions?

- Open an [Issue](https://github.com/yourusername/security-pulse/issues)
- Check [Discussions](https://github.com/yourusername/security-pulse/discussions)

---

**Built with ❤️ for the security community**
