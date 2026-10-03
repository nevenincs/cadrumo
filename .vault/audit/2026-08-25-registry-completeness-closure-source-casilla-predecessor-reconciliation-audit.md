---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-25'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:a8377c986087d7cc0cfefe3e1ff19ab2b24de82b843dc7f11727e63f68d8eeb1'
related: []
---

# `registry-completeness-closure` audit: `S35 source-casilla predecessor reconciliation`

## Scope

- `.vault/plan/2026-08-22-source-casilla-integration-plan.md`
- `dev/source_connectivity/{discovery,live_proof,check,cli}.py`
- `src/cadrumo/application/modelo/{_calculation_actions,_revision_persistence}.py`

## Method and no-redeclaration result

Vaultspec-RAG searched the vault for the source-casilla decision, plan, execution, census, and closure evidence, then searched production code for the live census proof, encrypted-revision match, and row-observation ingress. Whole-file reads covered the source plan, census, discovery, live-proof, coverage, authority, and current research records. Targeted `rg` then confirmed the exact symbols and all named plan rows.

There is no second source-connectivity authority to merge or delete. `assemble_observations_for_grouping` is the existing typed assembler, not a rival source resolver or persistence model. The exact file/symbol sweep found no duplicate census TOML, closure composer, live-proof authority, row identity model, or source-provenance carrier.

Scoped Ruff over the census, coverage, authority, discovery, check, and live-proof surfaces passed. `vaultspec-core vault plan check` passed with the existing PLAN022 ordering warning. A broad comparison/test run did not yield a completed result while concurrent worktree work was active, so this audit makes no broad-pass claim.

## Predicate-relevant matrix

| Plan rows | Current live evidence | Truthful state |
| --- | --- | --- |
| `S225` | Exact M036 profile binding/event coordinate, canonical profile resolver, lifecycle refusal of local filing, and terminal census row `censo.modelo-036-profile-status` | Implemented terminal `manual_by_design`; source-limb test proves it can satisfy only M036's scoped below-filing row. |
| `S92`-`S95` | M232 binding plus `per_related_party_operation` typed assembler; census row `rows.related-party-operation` | All open. No official semantic adjudication, durable source handoff, resolver enrollment, encrypted/replay/export proof, or review. `ingress_blocked` is a visible refusal, not completion. |
| `S96`-`S99` | M360 binding plus `per_refund_operation` assembler; `rows.refund-operation` | All open for the same reasons. |
| `S100`-`S103` | M182 donor binding plus `per_donativo_donor` assembler; `rows.donativo-donor` | All open. In particular, no official adjudication yet preserves Article-3 declarant/header, type-1 nature `3`, and administrator-holder identity without a lossy donor fold. |
| `S104`-`S107` | M193 bindings plus `per_gasto193_contribuyente` assembler; `rows.gasto193-contributor` | All open. No source semantics, resolver, persistence/replay/export proof, or review. |
| `S226`-`S233` | Grounded adjudications and independently reviewed execution records for M187, M220, M390, M721, M763, M840, M188, and M194 | All closed as evidence decisions. They add no runtime source owner, binding, casilla, producer, or census promotion: unsupported value lifecycles remain explicitly deferred or absent rather than inferred. |

The source coverage composer deliberately turns every current `ingress_blocked` candidate into a refused limb and every revision with no scoped census evidence into an unmeasured limb. This is required by the accepted closure ADR and proves that an owner, future deadline, or unchecked checkbox cannot satisfy the release predicate.

## Exact next implementation boundary: `W05.P14.S87`

`S87` is the shared first implementation dependency, but it is not authorization to invent a generic source, resolver, persistence store, provenance shape, or filing writer. It must define one application command that consumes the existing `assemble_observations_for_grouping(grouping, cells, revision, filing_year)` output under a validated snapshot and hands the typed observations to the existing calculation architecture. Its acceptance contract is:

2. Reuse, rather than redeclare, the secure calculation-revision carriers already accepted by `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`, `persist_calculation_revision`, and `CalculationRevision`: `row_binding_values`, `RowSourceIdentity`, `row_casilla_values`, `DirectRowMaterializationProvenance`, and `CalculationSourceRef`.
3. Preserve the selected registry revision, grouping, row index, binding identity, source identity, and content fingerprint to the source-specific resolver/handoff. `S87` cannot itself decide the legal fact, source ownership, collision policy, or a row-to-casilla mapping; those remain the separately grounded `S92`-`S107` slices.

The independent semantic work that can proceed in parallel with `S87` is `S92`: official M232 row semantics and source ownership. It cannot make M232 connected until the shared ingress and the M232-specific resolver/proof/review rows also land.

## Findings

### predecessor-open-surface | high | source-casilla campaign remains materially open

The predecessor plan currently has 99 open rows and 131 closed rows. The open set includes four deferred row vertical slices, inventory, amortization, finca, asset, recurring discovery, final census, documentation, focused gates, and final reviews. These are implementation and evidence gaps, not checkbox-only drift, so `W03.P06.S35` cannot close.

### adjudication-state-drift | low | M187 checkbox lagged reviewed evidence

`S226` had a complete execution record and independent approval but remained unchecked. The plan row is now CLI-closed. Rows `S226`-`S233` are all evidence decisions, and none is credited as a connected source or filing capability.

### closure-warning | low | audit schema sections were missing

This audit lacked the required Findings and Recommendations sections and contained mojibake range separators. The body now records the current matrix in valid UTF-8 and satisfies the attested audit schema.

## Recommendations

- Execute the shared ingress boundary beginning at `S87`, then close each source-specific vertical slice only from official semantics, secure persistence/replay, and supported export evidence.
- Re-run `S116` until two consecutive discovery passes are stable, then run `S117`; do not credit the earlier interrupted CLI state as closure evidence.
- Keep `W03.P06.S35` open until every predicate-relevant source row has a checked plan state, execution record, required review, and either a proven connected claim or an explicit terminal refusal.

## Conclusion

`W03.P06.S35` remains open. The predecessor campaign has one proven terminal M036 source boundary and eight completed below-filing adjudications, but the four declared deferred row families and the wider source-mesh implementation campaign remain explicitly open. No census disposition is promoted and no production or registry authority is changed by this reconciliation.
