"""Regression tests for the financial keyword tagger.

Pure functions only — no network, no state mutation. Run with:
    python -m pytest tests/ -q
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pulse import SecurityPulse  # noqa: E402


@pytest.fixture(scope="module")
def pulse():
    """A SecurityPulse bound to the real config (no feeds are fetched)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cwd = os.getcwd()
    os.chdir(root)
    try:
        yield SecurityPulse("config.yaml")
    finally:
        os.chdir(cwd)


# --- cross-tagging: must NOT fire (these were the measured false positives) ---

@pytest.mark.parametrize(
    "title,summary",
    [
        # ICS advisories tripped the naive matcher on stray terms.
        ("Mitsubishi Electric CC-Link IE TSN Communication Protocol",
         "ICS Advisory for industrial control systems. Successful exploitation "
         "could allow a remote attacker to cause a denial of service."),
        ("Siemens SIMATIC S7-1500 CPU 1518(F)-4 PN/DP MFP",
         "ICS Advisory. Vulnerability could allow an attacker to execute code."),
        # "card" in a non-payment sense
        ("Graphics card driver flaw allows privilege escalation",
         "A vulnerability in the graphics card driver lets attackers escalate."),
        ("Smart card reader vulnerability patched",
         "The smart card reader had an exploit allowing local compromise."),
        # Finance words but no cyber signal at all
        ("Bank of America raises quarterly dividend",
         "The bank announced a dividend increase for shareholders."),
        # Only a weak term, no strong term -> below min_score
        ("Fraud detection startup raises Series B",
         "The company uses machine learning for fraud detection."),
    ],
)
def test_does_not_tag(pulse, title, summary):
    assert pulse._is_financial_item(title, summary) is False


# --- cross-tagging: must fire (genuine hits observed in the live feeds) ---

@pytest.mark.parametrize(
    "title,summary",
    [
        ("Announcing the release of the Financial Services Cloud Security Playbook",
         "How financial institutions protect cloud environments from attack."),
        ("DORA: Safeguarding Europe's financial sector",
         "The regulation hardens the financial sector against cyber attack "
         "and incident response failures."),
        ("Interpol Leverages Global System to Curtail Fraud Payments",
         "Banks and payment networks coordinated to stop wire fraud and "
         "phishing-driven transfers."),
    ],
)
def test_does_tag(pulse, title, summary):
    assert pulse._is_financial_item(title, summary) is True


# --- KEV vendor matcher ---

@pytest.mark.parametrize(
    "vendor,product",
    [
        ("Cisco", "Secure Firewall Management Center (FMC)"),
        ("Fortinet", "FortiOS"),
        ("Oracle", "E-Business Suite"),
        ("Microsoft", "SharePoint"),
        ("Citrix", "NetScaler ADC"),
    ],
)
def test_kev_financial_true(pulse, vendor, product):
    assert pulse._is_financial_kev(vendor, product) is True


@pytest.mark.parametrize(
    "vendor,product",
    [
        ("Mitsubishi Electric", "CC-Link IE TSN"),
        ("Siemens", "SIMATIC S7-1500"),
        ("D-Link", "DIR-859 Router"),
    ],
)
def test_kev_financial_false(pulse, vendor, product):
    assert pulse._is_financial_kev(vendor, product) is False


# --- PYMNTS feed filter (looser gate: cyber/AI signal only) ---

PYMNTS_HEADLINES = [
    ("Grab Says AI Helps Company Move Items 30% Faster", "", True),
    ("Agentic Payments Turn Proof Into Competitive Advantage",
     "Agentic AI reshapes payments.", True),
    ("Bretton AI CEO Wants Banks to Kick the AI Tool Habit", "", True),
    ("FBI Agent Allegedly Admits to $1 Million Crypto Theft",
     "The agent compromised wallets in the attack.", True),
    ("Retailer Opens 12 New Storefronts in Ohio",
     "The chain expands its physical footprint.", False),
    ("Consumer Spending Rose 2% in July",
     "Households increased discretionary spending.", False),
]


@pytest.mark.parametrize("title,summary,expected", PYMNTS_HEADLINES)
def test_pymnts_filter(pulse, title, summary, expected):
    assert pulse._passes_feed_filter(title, summary, "financial") is expected


def test_pymnts_filter_pass_rate(pulse):
    """Guards against a filter that is either inert or far too strict."""
    passed = sum(
        1 for t, s, _ in PYMNTS_HEADLINES if pulse._passes_feed_filter(t, s, "financial")
    )
    assert 0 < passed < len(PYMNTS_HEADLINES)


def test_no_filter_keeps_everything(pulse):
    """Existing feeds have no `filter` key and must be unaffected."""
    assert pulse._passes_feed_filter("Anything at all", "", None) is True


def test_exclusion_vetoes_score(pulse):
    """An excluded vendor scores 0 even with strong finance terms present."""
    assert pulse._fin_score("Siemens financial institution banking breach") == 0


# --- link sanitisation (feed content is untrusted) ---

@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(document.cookie)",
        "JavaScript:alert(1)",
        "  javascript:alert(1)  ",
        "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
        "file:///etc/passwd",
        "vbscript:msgbox(1)",
        "",
        None,
    ],
)
def test_unsafe_links_dropped(pulse, url):
    assert pulse._safe_link(url) == "#"


@pytest.mark.parametrize(
    "url",
    [
        "https://thehackernews.com/2026/08/story.html",
        "http://example.com/feed/item?id=1&x=2",
        "HTTPS://UPPER.EXAMPLE.COM/x",
    ],
)
def test_safe_links_preserved(pulse, url):
    assert pulse._safe_link(url) == url.strip()


def test_no_unsafe_scheme_reaches_html(pulse):
    """End-to-end: a hostile feed link must not land in an href."""
    import datetime

    item = {
        "source": "Evil Feed",
        "title": "Click me",
        "link": pulse._safe_link("javascript:alert(document.cookie)"),
        "summary": "x",
        "date": datetime.datetime(2026, 8, 4),
        "is_new": True,
        "financial": False,
    }
    html = pulse.build_html({"security": [item]}, [], [], [])
    assert "javascript:" not in html
