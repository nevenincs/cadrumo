---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:ce1525c8e786b58c9d8350b3cf1e2b2382314b7bdad459cfe4e099c2e3548138'
step_id: 'S13'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---

# Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then run focused anti-regression tests structural audits locale and documentation gates feature-surface checks full tests and vault checks

## Scope

- `repository quality gates`

## Description

- Re-ground the repository and governing decision semantically, then confirm the
  live credential, custody, recovery, application, TUI, CLI, locale, and error
  registry symbols with exact searches.
- Exercise the complete feature surface with serial focused tests and run the
  repository's structural, locale, API-reference, documentation, and Vault
  gates without absorbing concurrent work.
- Verify retired password-policy symbols remain absent and recovery-secret
  operations remain independent of profile-password assessment.
- Record full-tree failures against their exact current-HEAD owners instead of
  describing a partially executed or deselected lane as green.

## Outcome

- The default credential/security lane passed: 67 passed and 82 integration
  cases deselected in 24.01 seconds. The integration credential, TUI, scripted
  CLI, locale, and public-boundary lane passed: 104 passed in 92.43 seconds.
- The serial custody default lane passed: 218 passed and 10 deselected in 78.42
  seconds. Custody exposes no integration-marked tests (228 deselected). The
  recovery public-boundary lane passed 22 tests and authentication mapping
  passed 27 tests. Recovery-artifact formatting verification passed Ruff lint,
  Ruff format check, and 7 capsule-envelope rotation tests.
- Feature-scoped Ruff lint passed. Exact negative searches found no production
  `NIST_PASSPHRASE_MIN_LENGTH`, `PROFILE_CUSTODY_PASSWORD_MIN_SCALARS`,
  `validate_profile_password`, or `map_profile_password_proof_failure`; the two
  custody names occur only as obsolete-symbol absence assertions. Recovery
  modules contain no profile-password assessment references.
- The feature-scoped Vault behavioral checks passed with two warnings: the
  feature index has 4 related links for 16 feature documents, and the reviewed
  S12 execution record requires refreshed lifecycle metadata. Neither warning
  identifies a runtime or security defect.
- The path-scoped feature surface is green. No in-scope production or test red
  was found.

## Notes

- Full-tree gates are not green because concurrent, non-feature work is
  incomplete. Import-linter kept 9 contracts and reported 1 existing layered
  architecture contract broken by application-to-adapter imports. Full Ruff
  lint reported unrelated diagnostics including SIM300 in locale tests, E501 in
  the facade export scanner, and RUF022 in the calculation registry; Ruff format
  reported 94 unrelated files needing formatting. No such file was modified.
- Locale scaffold check/audit reports broad Modelo schema-leaf drift (for
  example 275 missing Catalan leaves), with no profile-credential key in the
  reported failures. API-reference check/audit reports 4 missing, 2 orphan, and
  4 stale stubs owned by concurrent calculation, operator-surface, registry,
  and source-connectivity changes. The narrow API docs suite passed 10 tests and
  failed the matching stub-completeness test.
- Documented-command conformance passed 337 cases and failed one unrelated
  workstation agent-harness sequence that cites absent `aeat app agent
  --output`. The user-scope nitpicky build failed after 67.98 seconds with 13
  unrelated warnings/errors: seven generated casilla-200 markup warnings and
  six stale filing/modelo CLI-sequence frame counts.
- `just docs-check 4` was stopped safely after more than ten minutes at roughly
  93 percent with many failures/errors and no final count; the bounded gates
  above preserve exact actionable failures. No orphaned process from that run
  remained.
- The prescribed full corpus harness stopped at collectability after 142.20
  seconds: five unrelated agent-evaluation/harness modules import concurrent
  symbols that are absent from current HEAD. Consequently the harness-protected
  full two-lane run was not represented as executed. Feature-focused lanes and
  the complete serial custody lane remained authoritative for this change.
