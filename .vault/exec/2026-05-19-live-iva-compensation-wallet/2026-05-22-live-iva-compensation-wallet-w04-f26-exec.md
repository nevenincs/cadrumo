---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'W04.F26'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
  - '[[2026-05-21-live-iva-compensation-wallet-code-review-audit]]'
  - '[[2026-05-21-live-iva-compensation-wallet-persona-testimonials-audit]]'
---

# `live-iva-compensation-wallet` `W04.F26`

Redacted active profile bucket identifiers from top-level config repair output.

- Modified: `src/aeat/application/diagnostics.py`
- Modified: `src/aeat/application/test_diagnostics.py`

## Description

The config-domain repair pass found that `aeat config repair` still printed the
active profile bucket UUID in the profile summary and the `profile.storage`
diagnostic row. The same identifier could appear in JSON output through the
setup report.

The repair report now uses the generic `active_profile` marker in text output,
in `profile.storage` summaries, and in the JSON setup report. Readiness counts,
auth provider, check statuses, and recovery actions remain visible.

No destructive repair command was run. No live AEAT operation was performed in
this step.

## Tests

- `uv run pytest src/aeat/application/test_diagnostics.py -q --disable-warnings` completed with 31 passed.
- `uv run ruff check src/aeat/application/diagnostics.py src/aeat/application/test_diagnostics.py` passed.
- `uv run aeat config repair` completed without UUID-shaped active profile identifiers in the profile summary or `profile.storage` row.
- `uv run aeat --format json config repair` completed without UUID-shaped active profile identifiers in the setup `active_profile` field or `profile.storage` summary.
