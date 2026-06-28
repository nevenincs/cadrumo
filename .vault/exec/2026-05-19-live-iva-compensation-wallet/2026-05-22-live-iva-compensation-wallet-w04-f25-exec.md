---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'W04.F25'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
  - '[[2026-05-21-live-iva-compensation-wallet-code-review-audit]]'
  - '[[2026-05-21-live-iva-compensation-wallet-persona-testimonials-audit]]'
---

# `live-iva-compensation-wallet` `W04.F25`

Redacted active profile bucket identifiers from secure-object repair inventory.

- Modified: `src/aeat/application/repair_integrity.py`
- Modified: `src/aeat/application/test_repair_integrity.py`

## Description

The config-domain repair persona found that `aeat config repair list
<namespace> --unreadable`, which is now the safe next action for degraded
secure-object state, printed the active profile bucket UUID in row context and
embedded that UUID in active-bucket object-key hints.

The repair inventory now keeps the active bucket id internal to the digest
matching check. Rendered row context reports only `active_profile` and
placeholder key hints such as `transaction-catalogue:<active-profile>`. This
preserves useful row provenance and confidence signals without copying active
profile identifiers into terminal output or JSON inventory.

No destructive repair command was run. No live AEAT operation was performed in
this step.

## Tests

- `uv run pytest src/aeat/application/test_repair_integrity.py -q --disable-warnings` completed with 14 passed.
- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/_config/__init__.py` passed.
- `uv run aeat config repair list aeat.domain.transactions.bucket --unreadable` completed with redacted active-profile row context.
- `uv run aeat --format json config repair list aeat.domain.transactions.bucket --unreadable` completed with redacted active-profile row context.
- Text and JSON repair-list smoke checks found no UUID-shaped active profile identifiers in the output.
