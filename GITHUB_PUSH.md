# 🚀 Push to GitHub - Quick Start

## Step 1: Create Your GitHub Repository

1. Go to **https://github.com/new**
2. Fill in:
   - **Repository name:** `security-pulse`
   - **Description:** "Daily security vulnerability & AI risk feed aggregator"
   - **Public** ✓ (great for learning and getting feedback)
   - **Do NOT initialize** with README, .gitignore, or license (we have these)
3. Click **Create repository**

## Step 2: Connect Local to GitHub

Copy these commands into your terminal:

```bash
cd c:\Users\arsen\Documents\.venv\Projects\security-pulse
git remote add origin https://github.com/YOUR_USERNAME/security-pulse.git
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username.

## Step 3: Enable GitHub Actions

1. Go to your repo on GitHub
2. Click **Settings** → **Actions** → **General**
3. Under "Workflow permissions", select **Read and write permissions**
4. Click **Save**

## Step 4: Test the Workflow (First Run)

1. Go to **Actions** tab in your repo
2. Select **Daily Security Pulse** workflow
3. Click **Run workflow** → **Run workflow** (green button)
4. Watch it run! ✅
5. Check back in a minute - you should see `SECURITY_FEED.md` updated in your repo

## Step 5: Enable Scheduled Runs

The workflow is already set to run at **12:00 UTC daily**, but you can:

- Change the time in `.github/workflows/daily_pulse.yml` (edit the `cron` line)
- Run it manually anytime from the Actions tab

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `fatal: remote origin already exists` | Run `git remote remove origin` first |
| Workflow shows "permission denied" | Check Step 3 - enable write permissions |
| No files are being committed | Check `SECURITY_FEED.md` is being created locally first |
| Feeds aren't updating | Verify URLs in `config.yaml`, test locally with `python pulse.py` |

---

## What's Next?

After your first successful run:
- ✅ Star your own repo (for fun!)
- 📝 Add more feeds to `config.yaml`
- 🔧 Customize the schedule/output
- 📢 Share with security colleagues
- 🎯 Consider adding features (Slack webhooks, web dashboard, etc.)

---

**Need help?** Check GitHub's docs:
- [Creating a repository](https://docs.github.com/repositories/creating-and-managing-repositories/creating-a-new-repository)
- [GitHub Actions guide](https://docs.github.com/actions)
- [Configuring workflow permissions](https://docs.github.com/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)
