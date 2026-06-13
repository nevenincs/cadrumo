---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W04.F14'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# `live-iva-compensation-wallet` `W04.F14`

Added row-level secure-object repair context where it can be derived without payload decryption or private natural-key disclosure.

- Modified: `src/aeat/application/repair_integrity.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `src/aeat/application/test_repair_integrity.py`

## Description

The W04.F12 mitigation classified namespaces, but the row inventory still lacked bucket/profile and safe object-key context. This step extends each `aeat config repair list <namespace> [--unreadable]` row with:

- `context_bucket_id`
- `object_key_kind`
- `object_key_hint`
- `context_confidence`
- `context_note`

The context is intentionally conservative. Singleton catalogue namespaces can report `catalogue`; workflow state can report `state`; active-bucket transaction, usage-ratio, user-profile, and apoderado keys can report their active-bucket key shape. If the current master key proves the hint against the stored HMAC digest, the row reports `active_key_digest_match`; otherwise it reports repository-contract confidence or `unrecoverable_hmac_digest`.

Rows whose natural keys include taxpayer, expediente, snapshot, diagnostic, submission, or filing-period details remain redacted. No NIF/NIE, expediente id, wallet amount, filing content, or decrypted payload is printed.

No live AEAT operation was performed in this step.

## Tests

- `uv run pytest src/aeat/application/test_repair_integrity.py src/aeat/application/test_diagnostics.py -q --disable-warnings` completed with 39 passed.
- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py src/aeat/application/test_diagnostics.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/core/errors/registry/_adapters.py` passed.
