---
step_id: S461
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W05.P25.S461

## Step

Remove redundant `or "utf-8"` fallback at `providers/_csv.py:304` (`CSV_ENCODING_FALLBACK_CHAIN` already covers it).

## Outcome

- Removed ` or "utf-8"` suffix from `preferred = load_settings().financial_default_csv_encoding.strip()`.
- An empty `preferred` produces a `LookupError` on `bytes.decode("")` which is caught and the loop falls through to `CSV_ENCODING_FALLBACK_CHAIN` (which includes `"utf-8"`). Behavior is identical.
- 79 financial provider tests pass.

## Files touched

- `src/aeat/adapters/inbound/financial/providers/_csv.py`
