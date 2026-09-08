---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:2fd284e12fda16a3302b2a0f239891198aa6493f07421824c17e04ef524c035d'
step_id: 'S152'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only certificate-subject identity suggestion slice, including its adapter wrapper, application port and verb, exports, and dedicated tests, because no product setup surface consumes it.

## Scope

- `certificate adapter`
- `certificate-source application operations`
- `certificate identity tests`

## Changes

- `M` `src/cadrumo/adapters/outbound/aeat/auth/certificate.py`
- `M` `src/cadrumo/application/auth/certificate_source_operations.py`
- `D` `src/cadrumo/application/auth/tests/test_certificate_source_tax_id.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run ruff check src/cadrumo/application/auth/certificate_source_operations.py src/cadrumo/adapters/outbound/aeat/auth/certificate.py` -> `pass`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/auth/tests/test_certificate_sources.py src/cadrumo/application/auth/tests/test_certificate_sources_check.py src/cadrumo/application/auth/tests/test_certificate_sources_health.py src/cadrumo/adapters/outbound/aeat/auth/tests/test_certificate.py` -> `pass`
- `verify:` `rg -n "CertificateSubjectNifReader|certificate_source_tax_id|read_certificate_subject_nif" src dev .vault --glob '!*.pyc'` -> `pass` (only immutable historical audit references remain)
- `verify:` `uv run python -c "from dev.quality.unused_symbol_coverage import run_gate; ..."` -> `pass` (375 live symbols, 20 orphan tests, deleted identities absent)
