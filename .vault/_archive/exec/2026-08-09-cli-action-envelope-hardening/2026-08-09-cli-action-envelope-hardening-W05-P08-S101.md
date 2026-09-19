---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:43fad5c43eb31eeb6a17386e7c30c33f9636c4940bf1f372254f0434502939f6'
step_id: 'S101'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate application user-profile exception producers to typed catalogue/live-input verdicts or explicit terminal/no-recovery dispositions

## Scope

- `src/cadrumo/application/user_profile/_profile_repository.py`
- `src/cadrumo/application/user_profile/_bundle.py`
- `src/cadrumo/application/user_profile/_bundle_encryption.py`
- `src/cadrumo/application/user_profile/_censo_sync.py`
- `src/cadrumo/application/user_profile/_custody.py`
- `src/cadrumo/application/user_profile/_integrity.py`
- `src/cadrumo/application/user_profile/_login_session.py`
- `src/cadrumo/application/user_profile/_orchestration.py`
- `src/cadrumo/application/user_profile/_registration.py`
- `src/cadrumo/application/user_profile/_repository.py`

## Description

- Migrate every operator-facing refusal across the ten declared user-profile modules to its class registered message key.
- Carry the offending identity, version or failed condition as machine facts in place of the deleted sentences.
- Delete the duplicated sentences from refusals that already declared a key.
- Rewrite the assertions that matched on removed prose so they read the context instead.

## Outcome

- The declared package carries no operator-facing prose refusal; a rescan returns only the module facade's attribute protocol error.
- Every migration reused a key already registered against its error class, so no new locale leaf was required in any of the four catalogues.
- Two refusals had written out a recovery for the operator to follow: pass an explicit passphrase callback, or set the secret-store backend environment variable and retry. Both now carry the resolved and required backend as facts instead.
- Two exception-flattening sites were removed. The carry refusal stringified its cause and the profile repository restated a key it already declared; the cause survives as a registered error type.
- Six refusals in the censal identity path and five in the schema-version path had authored their operator text twice, once as prose and once as a key. Only the catalogue half was ever rendered, so the prose was dead weight.
- The bundle-lineage suite passes eight tests and the pointer suite eleven, both serially, and the package is lint clean.

## Notes

- Executed file by file with a test run between each, continuing the correction made at the preceding workflow step rather than the package-wide sweep used earlier in the campaign.
- Verification was scoped to the suites owning each changed file. A full package run is not currently readable: unrelated peer breakage fails a large share of it, confirmed by reading tracebacks rather than assumed. The signatures are a required tax-residence jurisdiction-scope flag missing from profile fixtures, a persisted-envelope schema mismatch raised from the storage adapters, a changed profile fact count, and a newly required IVA regime-composition fact. None of those paths were touched here.
- Carry-forward: none within the declared scope.
