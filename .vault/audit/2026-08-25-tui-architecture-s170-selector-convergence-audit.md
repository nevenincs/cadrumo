---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:af10ad0588f804b9edff8d114e0f339a62a96848ee0f2f8b619bb1d7f613e5ed'
related:
  - '[[2026-08-11-tui-architecture-plan]]'
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-08-25-tui-architecture-s170-plan-review-audit]]'
---
# `tui-architecture` audit: `S170 selector convergence code review`

## Scope

Independent formal code review of `W03.P20.S170` at frozen commit `a3dbaeee421`, after implementation commit `5dcd5a9c026` and boundary-hardening follow-up `82c906562d5`. The review checked the accepted canonical-defining-module amendment, plan amendment `cebbad34fe5`, PASS plan re-review `15cdb8b8bf7`, the S170 execution record, and the committed source and tests. It did not close or mutate the plan.

Discovery led with Vaultspec RAG over both code and ADR corpora, then read the canonical implementation and narrowed with exact `git grep` and AST evidence at the frozen commit. The live shared tree carried unrelated concurrent `core.directory_scan` relocation work, so every source conclusion used committed objects. A clean archive run of the focused selector, addressing, and fixed-point tests was stopped at the coordinator timebox after five passes and no failure; it is recorded as incomplete and is not represented as a full gate pass.

The exact census found the sole `ModeloWorkSelectorRequest`, `ModeloWorkResolution`, and `select_modelo_work_resolution` definitions in `src/cadrumo/application/modelo/work_addressing.py:189`, `src/cadrumo/application/modelo/work_addressing.py:227`, and `src/cadrumo/application/modelo/work_addressing.py:242`. The retired `_work_addressing.py` and `work_unit_selection.py` paths are absent; `_selectors.py` owns only calculation-revision selection; no source import names either retired module; and the Modelo package namespace binds none of the work-addressing family. All enumerated production, CLI, TUI, workflow, test, annotation, and local-import consumers use the public defining module directly, with no alias, shim, fallback, or compatibility path found.

The canonical selector is pure over the supplied `WorkUnitCatalogue` and resolved bucket: its AST contains no repository load, revisioned load, or active-bucket resolution. Visible all-state selection returns ABSENT for zero, resolves an active or discarded singleton, and rejects every multiple set before the revision assertion. Strict full-id selection is all-state and refuses absence. Operator lookup accepts only the typed 12-hex token, matches prefix or suffix, sorts by full id, and rejects ambiguity. Active-natural mode filters lifecycle state before applying the same zero/one/many policy. Exact target-coordinate assertions and natural revision assertion do not narrow a candidate set and run only after singleton cardinality. The remaining lifecycle list and aggregate scans are constraint-divergent, not substitutable target selectors.

Boundary parity is preserved: history translates malformed strict ids to its established `WorkUnitNotFoundError`; reconciliation retains its explicit cross-bucket refusal and translates scoped strict-id absence to the established not-found boundary. The real encrypted-SQL regression at `src/cadrumo/application/modelo/tests/test_work_addressing.py:170` captures with `load_revisioned`, mutates persisted catalogue state, instruments `secure_objects` SELECT statements around selection, and asserts zero post-capture SELECTs while returning the captured singleton.

The fixed-point proof is meaningful rather than a count ceiling: it parses current source, requires exactly one pure selector owner, rejects the retired definitions and files, checks direct imports for the explicit consumer census, rejects either retired module name across every Python import AST, and verifies the known substitutable scan consumers call the canonical selector without retaining their former loops.

## Findings

No critical, high, medium, or low finding remains in the reviewed S170 scope.

## Recommendations

PASS. Accept S170 implementation review without code remediation. Keep the plan row open until the coordinating owner performs the authorized lifecycle transition; this audit does not close the plan. The interrupted clean-archive run should not be cited as a complete suite, while the committed execution record's completed focused gates remain implementation provenance.
