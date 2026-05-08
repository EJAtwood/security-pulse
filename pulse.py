#!/usr/bin/env python3
"""
Security Pulse - Daily security vulnerability and AI risk aggregator
Fetches RSS feeds and generates a markdown security briefing.
"""

import feedparser
import yaml
import logging
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SecurityPulse:
    """Aggregates security feeds into a daily briefing."""
    
    def __init__(self, config_file: str = "config.yaml"):
        """Initialize with config file."""
        self.config = self._load_config(config_file)
        self.output_file = self.config.get("output", {}).get("file", "SECURITY_FEED.md")
        self.max_entries = self.config.get("output", {}).get("max_entries_per_feed", 5)
        self.timeout = self.config.get("fetch", {}).get("timeout", 10)
        
    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"✓ Loaded config from {config_file}")
            return config
        except FileNotFoundError:
            logger.error(f"✗ Config file not found: {config_file}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"✗ Error parsing YAML: {e}")
            raise
    
    def _fetch_feed(self, url: str) -> Optional[feedparser.FeedParserDict]:
        """Fetch a single RSS feed with error handling."""
        try:
            logger.info(f"  → Fetching: {url}")
            feed = feedparser.parse(url)
            
            # Check if feed was successfully parsed
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"  ⚠ Parse warning: {feed.bozo_exception}")
            
            return feed
        except Exception as e:
            logger.error(f"  ✗ Failed to fetch {url}: {e}")
            return None
    
    def _get_entry_date(self, entry: Dict) -> datetime:
        """Extract and parse publication date from feed entry."""
        try:
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                return datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                return datetime(*entry.updated_parsed[:6])
        except (TypeError, ValueError, AttributeError):
            pass
        return datetime.now()
    
    def fetch_pulse(self) -> str:
        """Fetch all configured feeds and generate markdown content."""
        content = f"# 🛡️ Security Pulse\n"
        content += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        content += "Latest vulnerability and AI-related security news from multiple sources.\n\n"
        content += "---\n\n"
        
        feeds_config = self.config.get("feeds", {})
        total_entries = 0
        
        for feed_key, feed_info in feeds_config.items():
            # Skip disabled feeds
            if not feed_info.get("enabled", True):
                logger.info(f"⊘ Skipped (disabled): {feed_info.get('name', feed_key)}")
                continue
            
            feed_name = feed_info.get("name", feed_key)
            feed_url = feed_info.get("url")
            
            if not feed_url:
                logger.warning(f"⚠ No URL for feed: {feed_name}")
                continue
            
            logger.info(f"📡 {feed_name}")
            feed = self._fetch_feed(feed_url)
            
            if not feed or not feed.entries:
                logger.warning(f"  ✗ No entries found or feed unreachable")
                content += f"## {feed_name}\n*No entries available*\n\n"
                continue
            
            # Sort entries by date if configured
            entries = feed.entries[: self.max_entries]
            if self.config.get("output", {}).get("sort_by_date", True):
                entries = sorted(entries, key=self._get_entry_date, reverse=True)
            
            content += f"## {feed_name}\n"
            for entry in entries:
                total_entries += 1
                title = entry.get("title", "Untitled")
                link = entry.get("link", "#")
                
                # Include description if configured
                if self.config.get("output", {}).get("include_description", False):
                    summary = entry.get("summary", "").replace("<[^<]+>", "")[:200]
                    content += f"- **[{title}]({link})**\n  > {summary}...\n"
                else:
                    content += f"- **[{title}]({link})**\n"
            
            content += "\n"
        
        logger.info(f"✓ Total entries aggregated: {total_entries}")
        return content
    
    def save_feed(self, content: str) -> None:
        """Save the generated content to markdown file."""
        try:
            with open(self.output_file, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"✓ Feed saved to {self.output_file}")
        except Exception as e:
            logger.error(f"✗ Failed to save feed: {e}")
            raise

    def _send_email(self, subject: str, body: str) -> None:
        """Send the generated feed via email if configured."""
        email_config = self.config.get("email", {})
        if not email_config.get("enabled", False):
            logger.info("Email delivery disabled in config")
            return

        smtp_server = os.getenv("EMAIL_SMTP_SERVER") or email_config.get("smtp_server")
        smtp_port = int(os.getenv("EMAIL_SMTP_PORT") or email_config.get("smtp_port", 587))
        smtp_username = os.getenv("EMAIL_USERNAME") or email_config.get("username")
        smtp_password = os.getenv("EMAIL_PASSWORD")
        email_from = os.getenv("EMAIL_FROM") or email_config.get("from")
        email_to = os.getenv("EMAIL_TO") or email_config.get("to")
        use_ssl = email_config.get("use_ssl", False)

        if not smtp_server or not smtp_username or not smtp_password or not email_from or not email_to:
            logger.warning("Email is enabled but SMTP configuration is incomplete. Skipping email send.")
            return

        recipients = [addr.strip() for addr in str(email_to).split(",") if addr.strip()]
        if not recipients:
            logger.warning("No email recipients configured. Skipping email send.")
            return

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = email_from
        message["To"] = ", ".join(recipients)
        message.set_content(body)

        try:
            logger.info(f"Sending email notification to: {recipients}")
            if use_ssl:
                smtp = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
            else:
                smtp = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
                smtp.starttls()
            smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)
            smtp.quit()
            logger.info("✓ Email sent successfully")
        except Exception as e:
            logger.error(f"✗ Failed to send email: {e}")

    def run(self) -> None:
        """Run the full pulse aggregation pipeline."""
        logger.info("=" * 60)
        logger.info("🚀 Security Pulse - Starting aggregation")
        logger.info("=" * 60)
        
        try:
            content = self.fetch_pulse()
            self.save_feed(content)
            email_subject = self.config.get("email", {}).get("subject", "Security Pulse Daily Digest")
            self._send_email(email_subject, content)
            logger.info("=" * 60)
            logger.info("✓ Security Pulse completed successfully!")
            logger.info("=" * 60)
        except Exception as e:
            logger.error(f"✗ Failed to complete Security Pulse: {e}")
            raise


if __name__ == "__main__":
    pulse = SecurityPulse()
    pulse.run()