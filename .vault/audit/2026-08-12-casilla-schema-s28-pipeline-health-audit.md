---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:139c87bb0f288b165d4c9a905df40b9a24e232ebc59adf4e57b8e9bcdefca645'
related:
  - "[[2026-08-10-casilla-schema-read-model-adr]]"
  - "[[2026-08-10-casilla-schema-plan]]"
---
# `casilla-schema` audit: `S28 pipeline-health persisted-readiness review`

## Scope

Reviewed the S28 delta in `src/cadrumo/application/overview/_pipeline_health.py`, `src/cadrumo/entrypoints/cli/tests/test_overview_pipeline_verb.py`, the exact S28 leaves in the Catalan, English, Spanish, and Hungarian locale catalogues, and the S28 execution record. The accepted read-model ADR and the `W03.P08.S28` plan row were the governing contract.

The review checked that conclusive filed lifecycle states alone retain precedence; every non-filed readiness state is derived from the latest persisted `VerificationReport` or the absence of one; finding severities remain display counters; the internal enum stem is `INCOMPLETO` while the wire value is `incomplete`; the parity test crosses the real CLI and encrypted `VerificationReportCatalogueRepository`; all four locale leaves resolve; and the delta stays within the declared shared-worktree surface.

## Findings

### [x] exec-hygiene | low | The S28 execution record retained scaffold annotations and one markdown-hygiene defect

The initial review found three template HTML comment blocks and one extra blank line in the S28 execution record. This did not weaken runtime behavior but prevented a warning-clean lifecycle claim.

Resolution: the execution record body was replaced through the VaultSpec CLI, removing all scaffold annotations and extra blank lines while preserving the implementation outcome, exact validation boundaries, and the two actual landing commits. The LOW finding is closed.

No runtime, authority, transport, persistence-test, localization, or worktree-boundary defect was found.

## Recommendations

Final verdict: PASS. S28 is ready for lifecycle closure.

Do not attribute the current tree-wide locale drift or the five pre-existing shared-helper integration failures to S28; their signatures are outside the reviewed delta and require their existing owners to reconcile them before a whole-tree green claim.

Focused evidence: the exact persisted-incomplete CLI regression passed; the typed pipeline-row transport regression passed; Ruff passed; BasedPyright reported zero errors, warnings, or notes; `git diff --check` passed; and direct runtime resolution produced the new summary and updated help in all four locales. The whole integration module reported two passes and five failures because `_create_profile` omits the now-required `--tax-residence-jurisdiction-scope`; the S28-owned regression uses a complete real profile and passed. `dev.locales scaffold --check` and `dev.locales audit` remain red only on unrelated profile-schema, IVA-wallet, dependency-help, and stale-ledger catalogue drift; neither gate named either S28 key.
