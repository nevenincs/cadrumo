---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:0b715e51deda00457f631309c0d34d29640e0c517c81edd109619a82daa23da2'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-adr]]'
  - '[[2026-06-03-modelo-export-workbook-parity-adr]]'
---

# `secure-storage-production-hardening` `W12.P26.S194` Review

## S194-001 | PASS | Profile source keeps storage ownership in profile binding resolution

`_source_profile.py` delegates profile-backed binding resolution to
`resolve_profile_sourced_bindings` and now consumes the
`ProfileSourcedBindingResult.profile_record_fingerprint` produced there. The
source-mesh resolver still does not construct repositories, read settings, inspect
environment variables, or own secure-storage routing. Bucket scope remains carried
by `CalculationSourceContext.bucket_id`.

## S194-002 | FIXED | Repository-loaded profile provenance retained

Initial review found a HIGH defect: when `ProfileSourceResolver` ran without an
injected `profile_record`, the runtime-loaded profile path returned profile
provenance with `fingerprint=None`. The fix moves profile fingerprint production
into `resolve_profile_sourced_bindings` after either the injected record or the
`UserProfileLifecycleRepository.load()` record has been selected, then carries
that value on `ProfileSourcedBindingResult`.

## S194-003 | FIXED | Fingerprint test is no longer tautological

Initial review found a LOW test weakness: the focused fingerprint assertion
mirrored the production hash expression and used ASCII-only profile data. The
test now uses a non-ASCII profile record and a pinned digest literal, plus a real
`isolated_runtime_profile` / `UserProfileLifecycleRepository` storage-loaded path
test. No mocks, fakes, stubs, monkeypatches, skips, or xfails were added.

## S194-004 | PASS | Export evidence ADR alignment

The resolver emits source-mesh provenance references of the form
`profile:{bucket_id}:binding:{binding_id}` and deterministic fingerprints for
profile-sourced facts. This supports the export evidence ADR direction that
ledger/profile-derived artefacts carry typed, attributable fact basis without
moving storage ownership into source-mesh contract code.

Validation:

- the historical check passed.
- the historical check passed with 4 tests.
- the historical check passed with 14 tests.
- the historical check passed with 8 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

Reviewer note: initial S194 review found one HIGH and one LOW issue; both were
remediated. A fresh reviewer re-review was attempted, but the subagent returned
an account usage-limit error before producing a report. Host review of the same
checklist found no remaining critical, high, medium, or low findings.

Disposition: close `AFR-092`.
