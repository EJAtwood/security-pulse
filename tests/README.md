# Tests for Security Pulse

`test_tagging.py` covers the pure, network-free logic:

- **Financial relevance tagging** — pins the known false positives (CISA ICS
  advisories matching stray `card` / `SEC`, "graphics card", finance stories
  with no cyber signal) and the genuine hits.
- **KEV vendor matching** — financial-sector software is flagged, OT/ICS
  vendors are not.
- **Per-feed content filter** — asserts the PYMNTS gate is neither inert nor
  so strict that the section empties.
- **Link sanitisation** — `javascript:`, `data:`, `file://` and other
  non-http(s) schemes must never reach an `href`.

Run them:

```bash
python -m pytest tests/ -q
```

Keyword lists live in `config.yaml`, so tuning them needs no code change —
but re-run this suite afterwards, since the false-positive cases are the
guardrail against a loosened rule.

These tests never fetch feeds and never touch `seen_items.json`.

> ⚠️ Running `python pulse.py` directly **does** mutate real state — it
> rewrites `SECURITY_FEED.md` and `seen_items.json`, which would burn items
> out of the next real digest. To test end to end, copy `config.yaml`, point
> `state.file` / `output.file` somewhere disposable, set `email.enabled: false`,
> and pass that config: `SecurityPulse("config.preview.yaml")`.
