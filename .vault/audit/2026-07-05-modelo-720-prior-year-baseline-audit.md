---
tags:
  - '#audit'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
  - "[[2026-07-05-modelo-720-prior-year-baseline-adr]]"
  - '[[2026-07-05-modelo-720-row-carrier-adr]]'
---
## Scope

Audited the W02.P03 Modelo 720 taxonomy implementation against the W02 plan, the M720 taxonomy ADR, BOE-grounded class-code intent, and the touched source/test files.

Audited implementation files: `src/aeat/core/aggregation.py`, `src/aeat/core/_foreign_asset_obligation.py`, `src/aeat/core/__init__.py`, `src/aeat/application/aggregation/_foreign_assets.py`, `src/aeat/core/tests/test_foreign_asset_obligation.py`, and `src/aeat/application/aggregation/tests/test_foreign_assets.py`.

Audited W03.P05.S13 source-mesh row-carrier implementation against the row-carrier ADR and the S13 plan row. The review covered the new row-binding carrier, merge ownership rules, JSON serialization shape, source-mesh readiness behavior, and the focused source-mesh tests.

Audited W03.P05.S14 foreign-assets resolver carrier implementation against the S14 plan row and row-carrier ADR. The review covered the resolver's handoff from registry row-value validation to `CalculationSourceResolution.row_binding_values`, the no-scalar-binding invariant, and the focused M720 resolver parity tests.

Audited W03.P05.S15 modelo replay implementation against the S15 plan row and row-carrier ADR. The review covered the structured `row_binding_values` replay payload, persisted revision identity, filing replay shape, real M720 draft row materialization, and the no-synthetic-scalar-id invariant.

Audited W03.P06.S16 and the campaign close as a fresh inherited surface against the plan, the row-carrier ADR, the source-mesh enrollment policy, the deferred-source partition, the foreign-assets resolver, the replay/persistence row-binding path, and the focused gates named in the S16 exec record.

## Findings

### import-boundary | medium | cross-package private import regressed the production import-hygiene gate

The first review pass found `src/aeat/application/aggregation/_foreign_assets.py` importing the new Modelo 720 class-code map and obligation helpers directly from `aeat.core._foreign_asset_obligation`. The focused runtime tests passed, but the repository import-hygiene gate proved this was a new production Family-1 violation. Resolution: `src/aeat/core/__init__.py` now exposes the foreign-asset obligation primitives from their owning source module, and `_foreign_assets.py` imports them from `aeat.core`. The real source remains `core._foreign_asset_obligation`; the facade is required only to satisfy the enforced package boundary.

### vault-trace | low | plan relation omitted the taxonomy ADR that governs W02.P03

The implementation steps were checked in the plan while the plan frontmatter still related only to the older June 2026 baseline ADR/research. Resolution: the plan now carries a related edge to `2026-07-05-modelo-720-prior-year-baseline-adr`, so W02.P03 traces to the taxonomy decision record. The ADR status remains `proposed`; that is preserved rather than silently promoted without an explicit ADR-approval action.

### s13-carrier-docstring | low | source-mesh carrier summary omitted the new row-indexed channel

The W03.P05.S13 review found the `CalculationSourceResolution` module summary still listing only the pre-existing scalar and detail-row channels. That stale summary could mislead the next row-carrier step into treating the carrier as ad hoc. Resolution: the source-mesh summary now names the row-indexed binding channel, and the focused S13 static and pytest gates pass after the correction.

### s13-json-replay | high | row-binding JSON replay corrupted numeric-looking text values

The W03.P05.S13 replay review found that the first JSON parser converted every serialized row-binding string through `Decimal` when possible. That preserved monetary fields but corrupted text fields such as asset identifiers: a value like `000123` replayed as a decimal and serialized back as `123`. Resolution: the row-binding JSON object now carries `value_kind`, replay restores only tagged decimal values as `Decimal`, and the source-mesh tests pin both decimal restoration and numeric-looking text preservation.

### s13-locale-catalogue | medium | new source-mesh diagnostics were missing from locale catalogues

The W03.P05.S13 review found the new row-binding validation diagnostics missing from the locale catalogues. Resolution: the locale scaffold added the source-mesh row-binding keys to every shipped locale catalogue, and both locale scaffold check and locale audit now pass.

### s16-close-trace | low | row-carrier ADR was missing from the plan related edge set

The close-honesty review found the S13-S16 implementation correctly following the row-carrier ADR but the plan frontmatter still did not list that ADR as an authorising related document. It also found stale registry and enum comments still naming `foreign_asset` as a deferred sibling. Resolution: `vaultspec-core vault link add` added `2026-07-05-modelo-720-row-carrier-adr` to the plan and to this audit, and the stale sibling lists now name only the still-deferred detail families. No code blocker was found: `foreign_asset` is enrolled in the live mesh, no new source kind or resolver convention was introduced, row values remain in `row_binding_values`, and replay/export keeps row ids out of scalar binding ids. The explicit `foreign_asset_observations` API is an intentional boundary because this campaign did not approve or add a durable foreign-asset observation store.

## Recommendations

- Keep W03 row-carrier work separate from this taxonomy commit; the new untracked row-carrier ADR placeholder is not part of the W02.P03 source migration.
- Before promoting the full feature to done, resolve or explicitly approve the taxonomy ADR status according to the ADR workflow.
- Continue to run the import-hygiene gate when changing cross-package imports; the production Family-1 gate is hard-zero.
- No additional S13 code-review blockers remain; proceed to downstream row-carrier steps only through the approved, replay-safe row-binding carrier.
- No S14 code-review defects were found; proceed to S15 by consuming `row_binding_values` directly rather than recomputing foreign-asset row values downstream.
- No S15 code-review defects were found; proceed to S16 by enrolling the existing foreign-assets resolver through the source mesh and preserving the structured row replay surface.
- No S16 code-review blockers remain. The Modelo 720 prior-year-baseline follow-up campaign can close with the row-carrier ADR edge now recorded and the existing S16 gates green.
