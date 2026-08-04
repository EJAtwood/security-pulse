#!/usr/bin/env python3
"""
Security Pulse - Daily security vulnerability and AI news aggregator.

Fetches RSS/Atom feeds plus the CISA Known Exploited Vulnerabilities (KEV)
catalog and produces:
  * a Markdown briefing (committed to the repo), and
  * a clean, card-based HTML email digest.
"""

import feedparser
import yaml
import json
import logging
import os
import re
import smtplib
import html as html_lib
from email.message import EmailMessage
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# --- Palette (inline styles only, for email-client compatibility) ---
C_BG = "#f4f5f7"
C_CARD = "#ffffff"
C_TEXT = "#1a2233"
C_MUTED = "#5b6472"
C_BORDER = "#e3e7ee"
C_LINK = "#1b56d3"
C_SECURITY = "#d64545"
C_AI = "#6d5bd0"
C_KEV = "#b3261e"
C_BADGE_RANSOM = "#b3261e"
C_BADGE_NEW = "#1a7f37"
C_FINANCE = "#0f766e"


class SecurityPulse:
    """Aggregates security + AI feeds into a daily briefing."""

    def __init__(self, config_file: str = "config.yaml"):
        self.config = self._load_config(config_file)
        out = self.config.get("output", {})
        self.output_file = out.get("file", "SECURITY_FEED.md")
        self.max_entries = out.get("max_entries_per_feed", 5)
        self.summary_length = out.get("summary_length", 220)
        fetch = self.config.get("fetch", {})
        self.timeout = fetch.get("timeout", 20)
        self.user_agent = fetch.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        )
        self.generated_at = datetime.now(timezone.utc)

        # Dedupe state: remembers what was already sent so the digest only
        # ever contains new items, even when feeds move slowly.
        state = self.config.get("state", {})
        self.state_file = state.get("file", "seen_items.json")
        self.lookback_hours = state.get("lookback_hours", 48)
        self.retention_days = state.get("retention_days", 30)
        self.recap_hours = state.get("recap_hours", 48)
        self.seen: Dict[str, Dict] = self._load_seen()
        self._compile_tagging()

    # ------------------------------------------------------------------- state
    def _load_seen(self) -> Dict[str, Dict]:
        """Load {item_id: {seen, title, source, category}} from the state file."""
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                seen = json.load(f)
            if not isinstance(seen, dict):
                return {}
            # Migrate legacy format where values were bare iso strings.
            seen = {
                k: (v if isinstance(v, dict) else {"seen": v})
                for k, v in seen.items()
            }
            logger.info(f"✓ Loaded {len(seen)} seen items from {self.state_file}")
            return seen
        except FileNotFoundError:
            logger.info(f"No state file yet ({self.state_file}); starting fresh")
            return {}
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"⚠ Corrupt state file, starting fresh: {e}")
            return {}

    def _save_seen(self) -> None:
        """Prune old entries and persist the seen-items state."""
        cutoff = self.generated_at.timestamp() - self.retention_days * 86400
        pruned = {}
        for item_id, meta in self.seen.items():
            try:
                ts = datetime.fromisoformat(meta.get("seen", "")).timestamp()
            except ValueError:
                continue
            if ts >= cutoff:
                pruned[item_id] = meta
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(pruned, f, indent=1, sort_keys=True)
        logger.info(f"✓ Saved {len(pruned)} seen items to {self.state_file}")

    def _mark_seen(self, item_id: str, **meta) -> None:
        self.seen[item_id] = {"seen": self.generated_at.isoformat(), **meta}

    def _collect_recap(self) -> List[Dict]:
        """Articles sent in PREVIOUS digests within the recap window."""
        cutoff = self.generated_at.timestamp() - self.recap_hours * 3600
        run_start = self.generated_at.isoformat()
        recap = []
        for item_id, meta in self.seen.items():
            if item_id.startswith("kev:") or not meta.get("title"):
                continue
            seen_iso = meta.get("seen", "")
            if seen_iso == run_start:
                continue  # sent in this run — already in the main sections
            try:
                if datetime.fromisoformat(seen_iso).timestamp() < cutoff:
                    continue
            except ValueError:
                continue
            recap.append(
                {
                    "link": self._safe_link(item_id),
                    "title": meta["title"],
                    "source": meta.get("source", ""),
                    "seen": seen_iso,
                }
            )
        recap.sort(key=lambda x: x["seen"], reverse=True)
        return recap

    # ------------------------------------------------------------------ config
    def _load_config(self, config_file: str) -> Dict:
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            logger.info(f"✓ Loaded config from {config_file}")
            return config
        except FileNotFoundError:
            logger.error(f"✗ Config file not found: {config_file}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"✗ Error parsing YAML: {e}")
            raise

    # ------------------------------------------------------------------- fetch
    def _http_get(self, url: str) -> Optional[bytes]:
        """Fetch a URL with a browser User-Agent (CISA/Akamai block bots)."""
        try:
            logger.info(f"  → Fetching: {url}")
            resp = requests.get(
                url,
                timeout=self.timeout,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/rss+xml,"
                    "application/atom+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                },
            )
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.error(f"  ✗ Failed to fetch {url}: {e}")
            return None

    def _fetch_feed(self, url: str) -> Optional[feedparser.FeedParserDict]:
        """Fetch and parse a feed, using a browser UA so feeds don't 403."""
        raw = self._http_get(url)
        if raw is not None:
            feed = feedparser.parse(raw)
            if feed.entries:
                return feed
            logger.warning("  ⚠ No entries after UA fetch; retrying via feedparser")
        # Fallback: let feedparser fetch directly.
        try:
            feed = feedparser.parse(url, agent=self.user_agent)
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"  ⚠ Parse warning: {feed.bozo_exception}")
            return feed
        except Exception as e:
            logger.error(f"  ✗ Feedparser failed for {url}: {e}")
            return None

    # -------------------------------------------------------------- utilities
    def _get_entry_date(self, entry: Dict) -> datetime:
        try:
            if getattr(entry, "published_parsed", None):
                return datetime(*entry.published_parsed[:6])
            if getattr(entry, "updated_parsed", None):
                return datetime(*entry.updated_parsed[:6])
        except (TypeError, ValueError, AttributeError):
            pass
        return datetime(1970, 1, 1)

    @staticmethod
    def _safe_link(url: str) -> str:
        """Allow only http(s) links through to the rendered output.

        Feed content is untrusted: a compromised or hostile feed could serve a
        `javascript:` or `data:` URL that would land in an href. Anything that
        is not plain http/https is dropped rather than rendered.
        """
        if not url:
            return "#"
        if re.match(r"^https?://", url.strip(), re.I):
            return url.strip()
        return "#"

    def _clean_summary(self, text: str, max_len: Optional[int] = None) -> str:
        max_len = max_len or self.summary_length
        if not text:
            return ""
        clean = re.sub(r"<[^>]+>", "", text)
        clean = html_lib.unescape(clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        if len(clean) > max_len:
            return clean[:max_len].rstrip() + "…"
        return clean

    # ----------------------------------------------------------------- tagging
    @staticmethod
    def _compile_terms(terms: List[str]) -> List:
        """Compile terms as whole-word, case-insensitive patterns.

        Entries containing a backslash are treated as raw regex so config can
        express things like "\\bABB\\b" when a bare word would be too greedy.
        """
        compiled = []
        for term in terms or []:
            if "\\" in term:
                pattern = term
            else:
                pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
            try:
                compiled.append(re.compile(pattern, re.I))
            except re.error as e:
                logger.warning(f"⚠ Skipping bad tagging pattern {term!r}: {e}")
        return compiled

    def _compile_tagging(self) -> None:
        """Precompile the financial tagging rules once per run."""
        cfg = self.config.get("tagging", {}).get("financial", {})
        self.tagging_enabled = bool(cfg.get("enabled", False))
        self.fin_min_score = cfg.get("min_score", 2)
        self.max_crossref = cfg.get("max_crossref", 6)
        self._fin_strong = self._compile_terms(cfg.get("finance_strong", []))
        self._fin_weak = self._compile_terms(cfg.get("finance_weak", []))
        self._cyber = self._compile_terms(cfg.get("cyber_terms", []))
        self._fin_exclude = self._compile_terms(cfg.get("exclude_patterns", []))
        self._kev_vendors = self._compile_terms(cfg.get("kev_vendors", []))
        if self.tagging_enabled:
            logger.info(
                f"✓ Financial tagging on "
                f"({len(self._fin_strong)} strong / {len(self._fin_weak)} weak terms, "
                f"min_score={self.fin_min_score})"
            )

    def _fin_score(self, text: str) -> int:
        """Weighted financial relevance score; 0 if any exclusion matches."""
        if not text:
            return 0
        if any(rx.search(text) for rx in self._fin_exclude):
            return 0
        score = 2 * sum(1 for rx in self._fin_strong if rx.search(text))
        score += sum(1 for rx in self._fin_weak if rx.search(text))
        return score

    def _has_cyber(self, text: str) -> bool:
        return bool(text) and any(rx.search(text) for rx in self._cyber)

    def _is_financial_item(self, title: str, summary: str) -> bool:
        """Cross-tag gate: needs finance signal AND cyber signal."""
        if not self.tagging_enabled:
            return False
        text = f"{title} {summary}"
        return self._fin_score(text) >= self.fin_min_score and self._has_cyber(text)

    def _passes_feed_filter(self, title: str, summary: str, filter_name: str) -> bool:
        """Per-feed content gate. No filter configured -> keep everything.

        The `financial` filter is deliberately looser than `_is_financial_item`:
        the feed is already a finance publication, so only a cyber/AI signal is
        required to keep the item.
        """
        if not filter_name:
            return True
        if filter_name == "financial":
            if not self.tagging_enabled:
                return True
            text = f"{title} {summary}"
            if any(rx.search(text) for rx in self._fin_exclude):
                return False
            return self._has_cyber(text)
        logger.warning(f"⚠ Unknown feed filter {filter_name!r}; keeping item")
        return True

    def _is_financial_kev(self, vendor: str, product: str) -> bool:
        """Does this KEV entry hit software common in financial-sector stacks?"""
        if not self.tagging_enabled:
            return False
        text = f"{vendor} {product}"
        return any(rx.search(text) for rx in self._kev_vendors)

    def _financial_crossrefs(
        self, feed_items: Dict[str, List[Dict]], kev: List[Dict]
    ) -> List[Dict]:
        """Finance-relevant items living in OTHER sections, as one-liners.

        These stay in their home section; this is an index, not a relocation.
        """
        if not self.tagging_enabled:
            return []
        refs = [
            {
                "title": f'{k["cve"]} — {k["name"] or k["vendor"]}',
                "link": k["link"],
                "source": "CISA KEV",
            }
            for k in kev
            if k.get("financial")
        ]
        others = [
            it
            for key, items in feed_items.items()
            if key != "financial"
            for it in items
            if it.get("financial")
        ]
        others.sort(key=lambda x: x["date"], reverse=True)
        refs += [
            {"title": it["title"], "link": it["link"], "source": it["source"]}
            for it in others
        ]
        return refs[: self.max_crossref]

    # ------------------------------------------------------------------- data
    def _collect_feed_items(self) -> Dict[str, List[Dict]]:
        """Return {category_key: [item, ...]} for all enabled feeds."""
        results: Dict[str, List[Dict]] = {}
        for feed_key, feed_info in self.config.get("feeds", {}).items():
            if not feed_info.get("enabled", True):
                logger.info(f"⊘ Skipped (disabled): {feed_info.get('name', feed_key)}")
                continue

            name = feed_info.get("name", feed_key)
            url = feed_info.get("url")
            category = feed_info.get("category", "security")
            feed_filter = feed_info.get("filter")
            feed_max = feed_info.get("max_entries", self.max_entries)
            if not url:
                logger.warning(f"⚠ No URL for feed: {name}")
                continue

            logger.info(f"📡 {name}")
            feed = self._fetch_feed(url)
            if not feed or not feed.entries:
                logger.warning("  ✗ No entries found or feed unreachable")
                continue

            entries = sorted(feed.entries, key=self._get_entry_date, reverse=True)

            cutoff = self.generated_at.timestamp() - self.lookback_hours * 3600
            items = []
            new_count = skipped_old = skipped_filter = 0
            for entry in entries:
                if len(items) >= feed_max:
                    break
                link = entry.get("link", "#")
                date = self._get_entry_date(entry)
                # Skip stale items (keep undated ones).
                if date.year > 1970 and date.timestamp() < cutoff:
                    skipped_old += 1
                    continue
                # Freshness policy: never repeat an item that was already sent.
                if link in self.seen:
                    continue

                title = entry.get("title", "Untitled").strip()
                summary = self._clean_summary(
                    entry.get("summary") or entry.get("description") or ""
                )
                # Content gate runs BEFORE _mark_seen: an item rejected today
                # must stay eligible if it becomes relevant later.
                if not self._passes_feed_filter(title, summary, feed_filter):
                    skipped_filter += 1
                    continue

                is_new = True
                new_count += 1
                items.append(
                    {
                        "source": name,
                        "title": title,
                        # Raw `link` stays the dedupe key; only the rendered
                        # value is scheme-restricted.
                        "link": self._safe_link(link),
                        "summary": summary,
                        "date": date,
                        "is_new": is_new,
                        # Cross-tag flag; redundant inside the financial section.
                        "financial": (
                            False
                            if category == "financial"
                            else self._is_financial_item(title, summary)
                        ),
                    }
                )
                self._mark_seen(
                    link,
                    title=title,
                    source=name,
                    category=category,
                )
            results.setdefault(category, []).extend(items)
            filtered_note = f", {skipped_filter} filtered out" if skipped_filter else ""
            logger.info(
                f"  ✓ {len(items)} items ({new_count} new, "
                f"{skipped_old} outside {self.lookback_hours}h window{filtered_note})"
            )
        return results

    def _collect_kev(self) -> List[Dict]:
        """Fetch the most recently added CISA KEV entries."""
        kev_cfg = self.config.get("kev", {})
        if not kev_cfg.get("enabled", False):
            return []
        raw = self._http_get(kev_cfg.get("url"))
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"  ✗ Failed to parse KEV JSON: {e}")
            return []

        vulns = data.get("vulnerabilities", [])
        vulns = sorted(vulns, key=lambda v: v.get("dateAdded", ""), reverse=True)

        max_entries = kev_cfg.get("max_entries", 8)
        max_age_days = kev_cfg.get("max_age_days", 14)
        age_cutoff = (
            self.generated_at.timestamp() - max_age_days * 86400
        )
        top = []
        new_count = 0
        for v in vulns:
            if len(top) >= max_entries:
                break
            cve = v.get("cveID", "")
            if not cve:
                continue
            # Only report recently added CVEs — never backfill old catalog entries.
            try:
                added = datetime.strptime(v.get("dateAdded", ""), "%Y-%m-%d")
                if added.replace(tzinfo=timezone.utc).timestamp() < age_cutoff:
                    break  # sorted desc by dateAdded, so everything after is older
            except ValueError:
                continue
            # Freshness policy: each CVE appears in exactly one digest.
            if f"kev:{cve}" in self.seen:
                continue
            v["_is_new"] = True
            new_count += 1
            top.append(v)
            self._mark_seen(f"kev:{cve}")
        logger.info(f"🔴 CISA KEV: {len(top)} recent ({new_count} new) of {len(vulns)} total")

        items = []
        for v in top:
            items.append(
                {
                    "cve": v.get("cveID", "—"),
                    "vendor": v.get("vendorProject", ""),
                    "product": v.get("product", ""),
                    "name": v.get("vulnerabilityName", ""),
                    "description": self._clean_summary(v.get("shortDescription", ""), 240),
                    "date_added": v.get("dateAdded", ""),
                    "due_date": v.get("dueDate", ""),
                    "ransomware": v.get("knownRansomwareCampaignUse", "Unknown") == "Known",
                    "is_new": v.get("_is_new", False),
                    "financial": self._is_financial_kev(
                        v.get("vendorProject", ""), v.get("product", "")
                    ),
                    "link": f"https://nvd.nist.gov/vuln/detail/{v.get('cveID', '')}",
                }
            )
        return items

    # ---------------------------------------------------------------- render
    def _section_defs(self) -> List[Dict]:
        return self.config.get(
            "sections",
            [
                {"key": "security", "title": "Vulnerabilities & Threats", "emoji": "🛡️"},
                {"key": "ai", "title": "AI News & Model Releases", "emoji": "🤖"},
            ],
        )

    def build_markdown(
        self,
        feed_items: Dict[str, List[Dict]],
        kev: List[Dict],
        recap: Optional[List[Dict]] = None,
        crossrefs: Optional[List[Dict]] = None,
    ) -> str:
        ts = self.generated_at.strftime("%Y-%m-%d %H:%M UTC")
        md = ["# 🛡️ Security Pulse", f"**Generated:** {ts}", ""]
        md.append(
            "Daily vulnerability, threat, AI-model, and financial-sector news "
            "from multiple sources."
        )
        md.append("\n---\n")

        if kev:
            md.append("## 🔴 Known Exploited Vulnerabilities (CISA KEV)\n")
            for k in kev:
                ransom = " · ⚠️ Ransomware" if k["ransomware"] else ""
                new_tag = "🆕 " if k.get("is_new") else ""
                fin_tag = "🏦 " if k.get("financial") else ""
                title = k["name"] or f'{k["vendor"]} {k["product"]}'.strip()
                md.append(f"### {new_tag}{fin_tag}[{k['cve']}]({k['link']}) — {title}{ransom}")
                meta = " · ".join(
                    p for p in [f"{k['vendor']} {k['product']}".strip(),
                                f"Added {k['date_added']}"] if p
                )
                md.append(f"*{meta}*\n")
                if k["description"]:
                    md.append(f"{k['description']}\n")
            md.append("---\n")

        for sec in self._section_defs():
            items = feed_items.get(sec["key"], [])
            if not items and not (sec["key"] == "financial" and crossrefs):
                continue
            items = sorted(items, key=lambda x: x["date"], reverse=True)
            if sec.get("max_items"):
                items = items[: sec["max_items"]]
            md.append(f"## {sec['emoji']} {sec['title']}\n")
            for it in items:
                new_tag = "🆕 " if it.get("is_new") else ""
                fin_tag = "🏦 " if it.get("financial") else ""
                md.append(f"### {new_tag}{fin_tag}[{it['title']}]({it['link']})")
                md.append(f"*{it['source']}*\n")
                if it["summary"]:
                    md.append(f"{it['summary']}\n")
            if sec["key"] == "financial" and crossrefs:
                md.append("**Also relevant from today's threat feeds:**\n")
                for r in crossrefs:
                    md.append(f"- [{r['title']}]({r['link']}) — *{r['source']}*")
                md.append("")
            md.append("---\n")

        if recap:
            md.append(f"## 📚 Earlier Articles (last {self.recap_hours}h)\n")
            for r in recap:
                src = f" — *{r['source']}*" if r["source"] else ""
                md.append(f"- [{r['title']}]({r['link']}){src}")
            md.append("")
        return "\n".join(md).rstrip() + "\n"

    def _card(self, inner: str, accent: str) -> str:
        return (
            f'<tr><td style="padding:0 0 14px 0;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="background:{C_CARD};border:1px solid {C_BORDER};'
            f'border-left:4px solid {accent};border-radius:8px;">'
            f'<tr><td style="padding:16px 18px;">{inner}</td></tr></table></td></tr>'
        )

    def _badge(self, text: str, color: str) -> str:
        return (
            f'<span style="display:inline-block;background:{color};color:#ffffff;'
            f'font-size:11px;font-weight:700;letter-spacing:.3px;padding:2px 8px;'
            f'border-radius:10px;margin-left:6px;vertical-align:middle;">{text}</span>'
        )

    def build_html(
        self,
        feed_items: Dict[str, List[Dict]],
        kev: List[Dict],
        recap: Optional[List[Dict]] = None,
        crossrefs: Optional[List[Dict]] = None,
    ) -> str:
        e = html_lib.escape
        ts = self.generated_at.strftime("%A, %B %d, %Y · %H:%M UTC")

        sec_counts = {
            s["key"]: min(
                len(feed_items.get(s["key"], [])),
                s.get("max_items", len(feed_items.get(s["key"], []))),
            )
            for s in self._section_defs()
        }
        total = sum(sec_counts.values()) + len(kev)

        rows: List[str] = []

        # KEV section
        if kev:
            rows.append(self._section_header("🔴", "Known Exploited Vulnerabilities", C_KEV,
                                             "CISA KEV catalog — actively exploited in the wild"))
            for k in kev:
                title = e(k["name"] or f'{k["vendor"]} {k["product"]}'.strip())
                badges = ""
                if k.get("is_new"):
                    badges += self._badge("NEW", C_BADGE_NEW)
                badges += self._badge("EXPLOITED", C_KEV)
                if k.get("financial"):
                    badges += self._badge("FINANCIAL", C_FINANCE)
                if k["ransomware"]:
                    badges += self._badge("RANSOMWARE", C_BADGE_RANSOM)
                meta_bits = [b for b in [e(f'{k["vendor"]} {k["product"]}'.strip()),
                                         f'Added {e(k["date_added"])}',
                                         (f'Due {e(k["due_date"])}' if k["due_date"] else "")] if b]
                inner = (
                    f'<div style="font-size:12px;color:{C_KEV};font-weight:700;">'
                    f'<a href="{e(k["link"])}" style="color:{C_KEV};text-decoration:none;">{e(k["cve"])}</a>'
                    f'{badges}</div>'
                    f'<div style="font-size:16px;font-weight:700;color:{C_TEXT};margin:6px 0 4px;">{title}</div>'
                    f'<div style="font-size:12px;color:{C_MUTED};margin-bottom:8px;">{" · ".join(meta_bits)}</div>'
                )
                if k["description"]:
                    inner += f'<div style="font-size:13px;color:{C_MUTED};line-height:1.5;">{e(k["description"])}</div>'
                inner += (
                    f'<div style="margin-top:10px;"><a href="{e(k["link"])}" '
                    f'style="font-size:13px;color:{C_LINK};text-decoration:none;font-weight:600;">'
                    f'View on NVD →</a></div>'
                )
                rows.append(self._card(inner, C_KEV))

        # Feed sections. Accent comes from config so new sections need no code.
        builtin_accents = {"security": C_SECURITY, "ai": C_AI, "financial": C_FINANCE}
        for sec in self._section_defs():
            items = sorted(feed_items.get(sec["key"], []), key=lambda x: x["date"], reverse=True)
            if sec.get("max_items"):
                items = items[: sec["max_items"]]
            is_financial = sec["key"] == "financial"
            if not items and not (is_financial and crossrefs):
                continue
            accent = sec.get("accent") or builtin_accents.get(sec["key"], C_SECURITY)

            subtitle = sec.get("subtitle")
            if is_financial:
                kev_fin = sum(1 for k in kev if k.get("financial"))
                if kev_fin:
                    plural = "s" if kev_fin != 1 else ""
                    subtitle = (
                        f'{subtitle} · {kev_fin} of today\'s {len(kev)} KEV CVE{plural} '
                        f'affect financial-sector software'
                    )
            rows.append(self._section_header(sec["emoji"], sec["title"], accent, subtitle))

            for it in items:
                date_str = it["date"].strftime("%b %d") if it["date"].year > 1970 else ""
                meta = e(it["source"]) + (f' · {date_str}' if date_str else "")
                new_badge = self._badge("NEW", C_BADGE_NEW) if it.get("is_new") else ""
                fin_badge = (
                    self._badge("FINANCE", C_FINANCE) if it.get("financial") else ""
                )
                inner = (
                    f'<div style="font-size:11px;color:{accent};font-weight:700;'
                    f'text-transform:uppercase;letter-spacing:.5px;">{meta}{new_badge}{fin_badge}</div>'
                    f'<div style="font-size:16px;font-weight:700;line-height:1.35;margin:6px 0 6px;">'
                    f'<a href="{e(it["link"])}" style="color:{C_TEXT};text-decoration:none;">{e(it["title"])}</a></div>'
                )
                if it["summary"]:
                    inner += f'<div style="font-size:13px;color:{C_MUTED};line-height:1.55;">{e(it["summary"])}</div>'
                inner += (
                    f'<div style="margin-top:10px;"><a href="{e(it["link"])}" '
                    f'style="font-size:13px;color:{C_LINK};text-decoration:none;font-weight:600;">'
                    f'Read article →</a></div>'
                )
                rows.append(self._card(inner, accent))

            # Compact index of finance-relevant items that live in other
            # sections — they are NOT moved, just linked from here.
            if is_financial and crossrefs:
                ref_rows = "".join(
                    f'<div style="padding:6px 0;border-bottom:1px solid {C_BORDER};">'
                    f'<a href="{e(r["link"])}" style="font-size:13px;color:{C_TEXT};'
                    f'text-decoration:none;font-weight:600;">{e(r["title"])}</a>'
                    f'<span style="color:{C_MUTED};font-size:12px;"> — {e(r["source"])}</span>'
                    f'</div>'
                    for r in crossrefs
                )
                inner = (
                    f'<div style="font-size:11px;color:{accent};font-weight:700;'
                    f'text-transform:uppercase;letter-spacing:.5px;">'
                    f'Also relevant from today\'s feeds</div>'
                    f'<div style="margin-top:8px;">{ref_rows}</div>'
                )
                rows.append(self._card(inner, accent))

        enabled_names = ["CISA KEV"] if self.config.get("kev", {}).get("enabled") else []
        enabled_names += [
            f.get("name", k)
            for k, f in self.config.get("feeds", {}).items()
            if f.get("enabled", True)
        ]
        source_names = ", ".join(enabled_names)

        new_total = sum(
            1 for items in feed_items.values() for it in items if it.get("is_new")
        ) + sum(1 for k in kev if k.get("is_new"))
        parts = [f"{new_total} new today", f"{len(kev)} exploited CVEs"]
        parts += [
            f'{sec_counts.get(s["key"], 0)} {s.get("count_label", s["key"])}'
            for s in self._section_defs()
        ]
        summary_line = " · ".join(parts)
        if total == 0:
            rows.append(
                f'<tr><td style="padding:20px 4px;">'
                f'<div style="font-size:14px;color:{C_MUTED};text-align:center;">'
                f'Quiet day — no items in the current window.</div></td></tr>'
            )

        # Collapsed recap of articles from previous digests (Gmail supports
        # <details>; clients that don't simply render it expanded).
        if recap:
            recap_rows = ""
            for r in recap:
                src = (
                    f'<span style="color:{C_MUTED};font-size:12px;"> — {e(r["source"])}</span>'
                    if r["source"] else ""
                )
                recap_rows += (
                    f'<div style="padding:6px 0;border-bottom:1px solid {C_BORDER};">'
                    f'<a href="{e(r["link"])}" style="font-size:13px;color:{C_TEXT};'
                    f'text-decoration:none;font-weight:600;">{e(r["title"])}</a>{src}</div>'
                )
            rows.append(
                f'<tr><td style="padding:14px 0 0 0;">'
                f'<details style="background:{C_CARD};border:1px solid {C_BORDER};'
                f'border-radius:8px;padding:14px 18px;">'
                f'<summary style="font-size:14px;font-weight:700;color:{C_MUTED};'
                f'cursor:pointer;">📚 Earlier articles — last {self.recap_hours}h '
                f'({len(recap)})</summary>'
                f'<div style="margin-top:10px;">{recap_rows}</div>'
                f'</details></td></tr>'
            )

        return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{C_BG};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{C_BG};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0"
 style="width:640px;max-width:100%;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <tr><td style="padding:0 0 20px 0;">
    <div style="background:{C_TEXT};border-radius:10px;padding:22px 24px;color:#fff;">
      <div style="font-size:22px;font-weight:800;letter-spacing:-.3px;">🛡️ Security Pulse</div>
      <div style="font-size:13px;color:#aeb6c6;margin-top:4px;">{ts}</div>
      <div style="font-size:13px;color:#dfe4ee;margin-top:12px;">{summary_line}</div>
    </div>
  </td></tr>
  {''.join(rows)}
  <tr><td style="padding:12px 4px 0;">
    <div style="font-size:11px;color:{C_MUTED};line-height:1.6;">
      Security Pulse aggregates {total} items daily from {source_names}.<br>
      Generated automatically via GitHub Actions.
    </div>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""

    def _section_header(self, emoji: str, title: str, accent: str, subtitle: Optional[str]) -> str:
        sub = (f'<div style="font-size:12px;color:{C_MUTED};margin-top:2px;">'
               f'{html_lib.escape(subtitle)}</div>') if subtitle else ""
        return (
            f'<tr><td style="padding:14px 0 10px 0;">'
            f'<div style="font-size:18px;font-weight:800;color:{accent};">{emoji} {html_lib.escape(title)}</div>'
            f'{sub}</td></tr>'
        )

    # ------------------------------------------------------------------ output
    def save_feed(self, content: str) -> None:
        try:
            with open(self.output_file, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"✓ Feed saved to {self.output_file}")
        except Exception as e:
            logger.error(f"✗ Failed to save feed: {e}")
            raise

    def _send_email(self, subject: str, text_body: str, html_body: str) -> None:
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

        if not all([smtp_server, smtp_username, smtp_password, email_from, email_to]):
            logger.warning("Email enabled but SMTP config incomplete. Skipping send.")
            return

        recipients = [a.strip() for a in str(email_to).split(",") if a.strip()]
        if not recipients:
            logger.warning("No email recipients configured. Skipping send.")
            return

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = email_from
        message["To"] = ", ".join(recipients)
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        try:
            logger.info(f"Sending email to: {recipients}")
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

    # --------------------------------------------------------------------- run
    def run(self) -> None:
        logger.info("=" * 60)
        logger.info("🚀 Security Pulse - Starting aggregation")
        logger.info("=" * 60)
        try:
            feed_items = self._collect_feed_items()
            kev = self._collect_kev()
            recap = self._collect_recap()
            crossrefs = self._financial_crossrefs(feed_items, kev)

            markdown = self.build_markdown(feed_items, kev, recap, crossrefs)
            html = self.build_html(feed_items, kev, recap, crossrefs)
            self.save_feed(markdown)

            subject = self.config.get("email", {}).get("subject", "Security Pulse Daily Digest")
            subject = f"{subject} — {self.generated_at.strftime('%b %d')}"
            self._send_email(subject, markdown, html)
            self._save_seen()

            logger.info("=" * 60)
            logger.info("✓ Security Pulse completed successfully!")
            logger.info("=" * 60)
        except Exception as e:
            logger.error(f"✗ Failed to complete Security Pulse: {e}")
            raise


if __name__ == "__main__":
    SecurityPulse().run()
