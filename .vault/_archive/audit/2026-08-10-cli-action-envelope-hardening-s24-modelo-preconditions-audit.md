---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:7bb4388d88983d65667c5f2a304970c492e7165be6ae040d1b7ed06661b6b946'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `s24 modelo preconditions`

## Scope

- Independently review the S24 application-owned modelo precondition records, verification-finding schema migration, producer-to-verdict totality, locale boundary, CLI projection compatibility, tests, and lifecycle readiness.
- Verify that calculate, verify, and file refusals expose canonical condition evidence and catalogue-derived recovery without retaining command prose, English fallbacks, or parallel recovery authorities.
- Reconcile the implementation against the accepted action-envelope architecture and the adjudicated modelo disposition partition.

## Findings

### s24-modelo-preconditions | high | stale missing-casilla test consumer used the retired call shape

The independent Terra xhigh reviewer found a test passing an obsolete second positional work-unit argument to `missing_required_casilla_finding`, whose canonical contract accepts only `casilla_id` positionally and requires `casilla_def` by keyword. Exact reconciliation found two more occurrences in the related provenance workflow test. All three consumers were corrected; production was not widened and no compatibility path was added. The direct language test passed once and the proportional missing-casilla selection passed 4 tests.

### s24-modelo-preconditions | medium | migrated cross-period blocks retained mixed line endings

The reviewer found `ruff format --check` red for `_verification_cross_period.py`. The project formatter was applied to that file only. Its semantic AST hash remained `ec9f9dfdfbf8a133f42efe3cdbf4e1a184c7607675d0eb96e8422ba8251a4857` before and after formatting; Ruff and Basedpyright then passed.

### s24-modelo-preconditions | low | canonical authority and localization checks pass

Calibrated RAG queries and exact `rg` and AST reconciliation found exactly one finding schema, one modelo precondition schema, one finding-to-precondition projection, 33 production finding constructors, and 67 unique profiles. No stale finding message or action field, application-layer localization call, or missing English, Spanish, Catalan, or Hungarian catalogue entry or placeholder remained. The CLI renderer derives message text from the locale key and typed facts and derives recovery only from the paired typed verdict.

### s24-modelo-preconditions | low | independent code verdict is PASS after remediation

The independent Terra xhigh review verdict is CODE PASS after the HIGH and MEDIUM findings were remediated and their focused tests and static checks passed. No critical or unresolved high-severity finding remains.

### s24-modelo-preconditions | low | lifecycle dependencies permit Step closure

The Vault CLI reports S24 as the next open Step with no missing execution mapping. The canonical action-verdict, catalogue, schema-resolution, storage, profile-guard, and persisted-workflow prerequisites are already closed. S25 and S26 consume the S24 application contract at CLI lifecycle and verification boundaries, while S27 proves the end-to-end recovery journeys; they are successors and remain open.

### s24-modelo-preconditions | low | broad-suite failures remain external and bounded

The broader affected suite is not globally green: concurrent Modelo 303 registry and locale work caused 76 registry-authority failures after 121 passes, and one proportional cross-period test fails because the existing seven-character `AEAT-2T` justificante fixture no longer satisfies the eight-character schema minimum. Focused S24 locale, renderer, producer, schema, and static gates pass; the external failures are recorded without being recast as S24 evidence.

## Recommendations

- Accept the remediated S24 implementation and close S24 only.
- Keep S25, S26, and S27 open so CLI lifecycle projection, verification continuation binding, and negative-recovery-retry journeys remain explicit downstream work.
- Preserve the typed finding and precondition ratchets so a new producer, locale key, or action-bearing field must satisfy the canonical schema and live catalogue.
- Resolve the concurrent Modelo 303 registry and locale work and update the stale justificante fixture in their owning work before claiming a broader suite pass.
