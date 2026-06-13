---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'W04.F24'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
  - '[[2026-05-21-live-iva-compensation-wallet-code-review-audit]]'
  - '[[2026-05-21-live-iva-compensation-wallet-persona-testimonials-audit]]'
---

# `live-iva-compensation-wallet` `W04.F24`

Made auth diagnostics list an inventory surface instead of a profile/identity report.

- Modified: `src/aeat/application/auth/_diagnostics.py`
- Modified: `src/aeat/application/auth/test_diagnostics.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`

## Description

The config-domain persona pass found that `aeat config auth diagnostics list`
printed active-profile labels/ids, DNI/NIE identity kind, and profile-alignment
context while the operator was only asking for diagnostic inventory. That output
is too easy to copy into audit notes or issue comments.

List mode now disables private auth-attempt context at the application boundary.
The text renderer prints diagnostic id, timestamp, reason, mode, headless flag,
phone-state report, and capture flags. JSON list output keeps schema fields
stable but emits empty or null profile/identity/credential context. The
deliberate detail surface remains `aeat config auth diagnostics show <id>`,
where values are still redacted or fingerprinted.

No live AEAT operation was performed in this step.

## Tests

- `uv run pytest src/aeat/application/auth/test_diagnostics.py -q --disable-warnings` completed with 1 passed.
- `uv run aeat config auth diagnostics list` completed without printing profile labels/ids or identity kind.
- `uv run aeat --format json config auth diagnostics list` emitted empty/null profile and identity context fields in list rows.
- `uv run pytest src/aeat/application/auth/test_diagnostics.py src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py src/aeat/application/user_profile/test_profile_repository.py src/aeat/application/workflow/test_state_persistence_roundtrip.py src/aeat/application/auth/test_operator.py src/aeat/application/test_state_projection.py src/aeat/application/test_diagnostics.py src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_error_registry_contract.py -q --disable-warnings` completed with 146 passed.
- `uv run ruff check src/aeat/application/auth/_diagnostics.py src/aeat/application/auth/test_diagnostics.py src/aeat/entrypoints/cli/_config/__init__.py` passed.
