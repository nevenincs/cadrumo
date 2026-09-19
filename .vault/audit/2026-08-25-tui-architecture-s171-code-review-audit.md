---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:dd71cdc0d0503fe44f2cf7ec77d7da621b464de42df49261f7fba1d058e64e86'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-08-25-tui-architecture-s171-plan-review-audit]]"
---
# `tui-architecture` audit: `S171 Workspace model relocation code review`

## Scope

Independent formal code review of `W03.P20.S171` at frozen committed state `61edebe59f`, combining relocation provenance `3ec3f7908a`, implementation `1d13b76fbe`, the required-nullable model correction in `06e55cfadd`, and its negative omission proof and execution-record update in `61edebe59f`. The review compared the code with the accepted Workspace ADR, amended plan, architecture and plan-review audits, contract reference, and S171 execution record. The plan row remains open.

Discovery led with Vaultspec RAG and then closed every conclusion with immutable whole-file reads plus exact `git grep` and AST-oriented import inspection. At the final frozen state, `workspace_models.py` is the sole public defining module; all five Python consumers import it directly; the private source and API-document paths are absent; `application.modelo` is inert and exports nothing; and no evaluator, registry read, loader, repository, or I/O operation exists in the model module. The two fixed-source assertion axes, explicit required-nullable asserted id, closed outcomes and combinations, exact typed mismatch-source set, old-field refusal, identical contributor epoch digest across baseline/facet/cursor, full cursor validators, unavailable-facet rule, and strict round trips are correctly implemented.

Relocation history was not atomic: `3ec3f7908a` renamed the source and API-stub paths while five source/test consumers plus the root API document and drift disposition still named `_workspace_models`; `1d13b76fbe` later converged them. The final tree is clean, but this historical non-atomic interval is recorded as a delivery-process deviation rather than presented as an atomic hard move.

## Findings

### cursor-coordinate-bite-matrix | medium | Cursor consistency code is stricter than its committed regression proof

`src/cadrumo/application/modelo/workspace_models.py:643` validates a cursor against its baseline contract version, selected revision, schema identity, and contributor epoch digest; the bounded facet additionally enforces the `has_more`/`next_cursor` equivalence at line 748 and the complete cursor coordinate at line 750. The committed test at `src/cadrumo/application/modelo/tests/test_workspace_models.py:627` changes only the nested cursor facet and the outer facet epoch digest. Its unavailable case supplies `has_more = true` together with a cursor, so it does not bite the equivalence validator. It never independently changes the cursor baseline, contract version, selected revision, schema identity, or cursor epoch digest. Removing any one of those validator limbs, or the `has_more` equivalence branch, can therefore leave the committed suite green. This fails S171's required one-coordinate-change and digest-consistency gate even though the current production validators are correct.

## Recommendations

FAIL. Add a parametrized negative matrix built from one valid available page and cursor. Change exactly one of baseline, cursor contract version, selected revision, schema identity/fingerprint, facet, and cursor contributor epoch digest per case; prove both `has_more` mismatch directions; retain the unavailable-with-record/cursor cases and strict JSON round trip. Demonstrate that each validator limb bites, rerun the focused model/producer/manifest suites sequentially, and append a remediation re-review here. Do not close the plan row until that proof passes.

## Remediation re-review

### Scope and evidence

Fresh independent re-review of remediation commit `000700468f4c09396c828d790b5576ec37507f4e` against the open MEDIUM above. The committed diff changes only the focused Workspace model test and the S171 execution evidence. The production validators are unchanged. A sequential independent run of `src/cadrumo/application/modelo/tests/test_workspace_models.py` at a live tree whose reviewed files are byte-identical to the remediation commit passed all 28 tests.

### Prior finding closure

The `cursor-coordinate-bite-matrix` MEDIUM is closed. The parametrized proof creates one valid cursor/page and changes exactly one of the cursor baseline identity, contract version, selected revision, schema identity/fingerprint, facet, or contributor epoch digest. A singleton-delta assertion prevents a case from accidentally changing multiple coordinates. Baseline and facet changes reach the bounded-facet complete-coordinate validator; contract version, selected revision, schema identity, and epoch changes reach the typed cursor's own baseline-consistency validators, as proven by their exact branch-specific error messages.

The page-state proof independently exercises both disagreement directions: `has_more = true` with no cursor and `has_more = false` with a cursor. A separate mutation changes only the outer facet epoch digest relative to its baseline, and the unavailable mutation retains the otherwise-valid cursor/page state so the unavailable-payload validator itself refuses it. Every refusal is constructed through the real Pydantic model boundary without mocks, monkeypatches, helper-side emulation, or an expected value derived from the assertion under test.

### Remediation disposition

PASS. Commit `000700468f4c09396c828d790b5576ec37507f4e` closes the sole MEDIUM; no HIGH or MEDIUM finding remains in the reviewed S171 current-state implementation. The original FAIL and the historical non-atomic relocation provenance above remain preserved as the record of the first review. This re-review does not modify or close the plan row.
