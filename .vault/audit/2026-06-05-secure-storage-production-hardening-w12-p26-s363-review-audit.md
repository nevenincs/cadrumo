---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-08-15'
body_hash: 'sha256:f9cd4fc72b966bd0cc60fd12607c34a427a04262768defac17bc75a2363cc532'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S363` Review

## S363-001 | PASS | Preflight does not own storage or remote IO

`_preflight.py` calls injected `DeadlineWindowChecker` and `AuthProviderProbe`
protocols only. It does not instantiate secure-object repositories, resolve active
profiles, read settings, inspect environment variables, dereference filesystem paths,
or call remote-provider clients directly.

## S363-002 | PASS | Refusals are localized and structured

Every refusal path raises `SubmissionPreflightError` with an
`errors.refused.submission_preflight_*` locale key and structured context. Auth
provider describe failures are logged with `exc_info=True` and chained into the
preflight error instead of being swallowed.

## S363-003 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/domain/submission/_preflight.py src/aeat/adapters/outbound/aeat/export/tests/test_preflight.py` passed.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/export/tests/test_preflight.py` passed with 9 tests.
- `uv run --no-sync pytest -q src/aeat/application/workflow/tests/test_engine.py -k "preflight"` passed with 5 selected tests.

Reviewer note: no critical, high, medium, or low secure-storage findings remain for
the S363 policy slice.

Disposition: close `AFR-261`; scanner signals are protocol-policy provenance, not
direct storage or remote-provider behavior.
