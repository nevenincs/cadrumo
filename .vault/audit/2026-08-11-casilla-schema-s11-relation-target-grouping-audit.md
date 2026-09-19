---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:a657fbbf4ca42686036cfaac7e1d3996b23607850fa3061bc40514c80238723b'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-canonical-derivations-adr]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S11 canonical relation target grouping`

## Scope

Reviewed W02.P03.S11 against the accepted canonical-derivations decision, campaign plan, research, and repository quality constraints. The scoped production surfaces were `_queries.py`, the registry facade, and `_relation_prefill.py`, with the real registry regression in `test_queries.py`. The required contract is one public grouping from each `target_binding` to its declared `RelationDefinition` rows, preserving registry declaration order, with both query copies and the relation-prefill copy retargeted and no compatibility or private duplicate retained.

## Findings

No actionable findings.

`relations_by_target_binding` is the sole grouping loop in the scoped production surface. It traverses `revision.relations` once, creates binding keys on first encounter, appends relation objects in declaration order, and freezes every group to a tuple. The registry facade explicitly imports the same function and lists it in its public `__all__`; consumers do not reach into `_queries` privately.

Both query consumers now delegate grouping to the canonical function. `_relation_inputs_by_target_binding` performs only its own period filter and relation-id projection over the ordered canonical groups, retaining order and omitting empty filtered groups. `_operator_input_required_by_binding` performs only the M202 input-required decision over those groups. `relation_prefill_period_zero_default_binding_ids` likewise imports the public facade function and retains its original source-kind, period, relation-kind, and same-model checks. No compatibility alias, fallback, private mapper, or second grouping loop remains in these files.

The real M202 2025 annual snapshot regression imports the public facade function and names two target bindings with two relations each whose declaration order differs by target-period applicability. Its expected relation-id tuples are fixed registry-authoritative observations rather than a reimplementation of the grouping loop. The test uses no fake, stub, mock, patch, monkeypatch, skip, or expected-failure construct.

The repository also contains relation indexes at other documented grains, including producer inventory and validation. The accepted decision explicitly leaves `CasillaProducerInventory` untouched; those surfaces do not redeclare the three query/prefill grouping copies owned by S11.

## Verification

- Owning query module plus two focused M202 relation-prefill controls: 25 passed, 2 failed.
- Both failures are unrelated existing M303 localization drift: query rendering requests missing Spanish key `modelo.schema.303.revision.2026-y-siguientes.casilla.500.label` before any S11 grouping assertion. The new real declaration-order regression and both M202 zero-default controls passed in the same lane.
- Scoped Ruff: passed.
- Scoped BasedPyright: 0 errors, 0 warnings, 0 notes.
- Scoped `git diff --check`: passed; Git additionally emitted only its existing CRLF-to-LF warning for `_queries.py`.
- Prohibited test-construct scan: no hits.
- Retired-loop sweep: the only `revision.relations` plus `setdefault(target_binding)` grouping in the scoped production files is the canonical function itself.
- Facade inspection: one explicit import and one public `__all__` entry for `relations_by_target_binding`.

## Recommendations

No corrective action is required for S11. Resolve the unrelated M303 Spanish label gap in its owning localization/registry workstream; do not widen this step or introduce rendering tolerance.

Verdict: **PASS.** W02.P03.S11 establishes the one public relation-target grouping and retargets all three owned duplicates while preserving declaration order and consumer-specific filtering.
