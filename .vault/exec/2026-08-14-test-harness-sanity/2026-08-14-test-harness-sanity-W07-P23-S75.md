---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:061ce6ab4988ff8037bf7f423f6f21c62ded0cee8b4b800c968f554134ff31f2'
step_id: 'S75'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Replace the OFX optional-extra monkeypatch with real behavior

## Scope

- `src/cadrumo/adapters/inbound/financial/providers/tests/test_ofx.py`

## Description

- Remove the OFX availability monkeypatch from routine unit coverage.
- Exercise the installed-extra path in the normal environment and the absent-extra path in a real locked bare-core child process.
- Keep the installed-environment proof in ordinary integration and bound subprocess execution with diagnostics.

## Outcome

OFX optional-extra behavior is now tested without mutating imports or production symbols. The normal environment proves real OFX parsing with the extra installed, while an isolated locked environment proves the typed unavailable-extra envelope when the default dependency set omits it.

## Notes

The first replacement created and installed an editable virtual environment inside a unit test and was rejected for routine-lane cost. A second review rejected `serial` routing and network-refresh behavior. The final proof uses `uv run --isolated --locked --no-default-groups`, passes with inherited `UV_OFFLINE=1`, carries a 90-second timeout, and remains outside unit selection. Focused unit, integration, offline integration, Ruff, marker, and no-monkeypatch checks passed; the repository gate remains red only for S76-S78 sites.
