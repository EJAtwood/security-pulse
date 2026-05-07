# Setup Instructions

## One-Time Setup

### 1. Initialize Git (Already Done)
```bash
git init
```

### 2. Create GitHub Repository
- Go to https://github.com/new
- Name: `security-pulse`
- Description: "Daily security vulnerability & AI risk feed aggregator"
- Public repository
- Don't initialize with README
- Click Create

### 3. Add Remote & Push
```bash
git remote add origin https://github.com/YOUR_USERNAME/security-pulse.git
git branch -M main
git add .
git commit -m "Initial commit: Security Pulse automation setup"
git push -u origin main
```

### 4. Enable GitHub Actions
- Go to your repo Settings
- Actions → General
- Set "Workflow permissions" to "Read and write permissions"
- Save

### 5. Test the Workflow
- Go to Actions tab in GitHub
- Click "Daily Security Pulse"
- Click "Run workflow" → "Run workflow"
- Watch it execute!

## Local Development

### Install Dependencies
```bash
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Run Locally
```bash
python pulse.py
```

### View Output
```bash
cat SECURITY_FEED.md
```

### Modify Configuration
Edit `config.yaml` to add/remove feeds or adjust settings.

## Troubleshooting

**Q: How often does it run?**
A: By default, 12:00 UTC daily. Change `cron` in `.github/workflows/daily_pulse.yml`

**Q: Can I run it manually?**
A: Yes! Go to Actions → Daily Security Pulse → Run workflow

**Q: How do I add a new feed?**
A: Edit `config.yaml` and add an entry under `feeds:`

**Q: It's not working!**
A: Check the Actions tab for error logs. Verify feed URLs are accessible.
