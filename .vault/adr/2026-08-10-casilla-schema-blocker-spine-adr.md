---
tags:
  - '#adr'
  - '#casilla-schema'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:28feba53146de965c6f1a826603f1e9d76946a12343c93c2d3b8c917a8906b08'
related:
  - "[[2026-08-10-casilla-schema-research]]"
  - "[[2026-06-10-cli-envelope-notice-standardisation-adr]]"
---

# `casilla-schema` adr: `an operator action spine over the blocker vocabularies` | (**status:** `accepted`)

## Problem Statement

Roughly 20 closed vocabularies with ~800 members describe "something is wrong", connected by 11 ad-hoc mappings; two duplicate enums carry the same four concepts with incompatible wire tokens; and one collapse squashes 21 typed blocker codes into prose (`2026-08-10-casilla-schema-research`, Q5 and B-01/B-07). No surface can render a consistent what-to-do-next column.

## Considerations

- A total-by-construction mapping exemplar already ships: `BLOCKING_REASON_BY_DISCREPANCY_KIND` raises at import when a member is unmapped.
- Only 5-6 vocabularies reach operator surfaces; the rest never need projection.
- Per-domain precision is load-bearing (each code names an exact defect); losing it to a merged enum would degrade refusals.
- The `Notice` spine already carries a typed `context` map for machine facts.
- There is no released data, so a duplicate-enum deletion has no wire-compat burden.

## Considered options

- **One merged enum (~800 members)** - rejected: destroys per-domain precision and every gate keyed to the native enums.
- **A declared mapping lattice between vocabularies** - rejected: N-squared growth is why only 11 mappings exist today.
- **A small spine enum plus one total projection per surface-reaching vocabulary** - chosen.

## Constraints

- Every projection must be total by construction with an import-time refusal, following the exemplar exactly; a partial mapping table is worse than none.
- The native code always travels WITH the spine value (pair, never replacement); no machine detail may be dropped.
- The `DiscrepancyCause` / `VerificationDiscrepancyCause` reconciliation is one atomic commit: pick one, sweep every consumer, delete the other - no alias, no bridge.

## Implementation

A new core StrEnum `OperatorActionAxis` (the name is settled, not provisional) whose members each name one distinct operator ACTION class. Provisional seed list, amendable during the projection mapping steps without a new decision record: supply_manual_input, import_ledger_data, set_profile_fact, file_prior_period, capture_external_evidence, resolve_value_divergence, re_verify, resolve_revision_mismatch, confirm_group_membership, resolve_identity, complete_document_evidence, review_advisory. The enum lands first, seeded from this list; a projection step that discovers a missing action class adds the member in the same commit as the mapping that needs it.

Each surface-reaching vocabulary declares one total projection table beside its own enum in its owning layer, asserted total at import: `CrossPeriodCleanStateBlocker` (21 members, `application/calculations`), `ModeloVerificationFindingKind` (7, `domain/modelos`), the `modelo.readiness` payload's three lists - `missing`, `missing_bindings`, `ledger_issues`, the shape the trail calls the readiness triple - projected where the payload is assembled, `IvaLedgerAggregationIssueReason` on the preflight path (`application/ledger/_preflight.py`), and `ConfirmationBlockReason` beside its core enum (a core-to-core mapping). Finding `message_facts` are copied into `Notice.context` so blocker codes reach the envelope as data, closing the undocumented half of the fact-loss finding. The duplicate discrepancy enums are reconciled to one and the loser deleted in the same commit as its consumer sweep; their homes are `application/verification/_schema.py` and `domain/calculations/registry/_schema_verification.py`, and the reconciliation coordinates with the dead-surface ADR's package deletion, which owns the first home.

One adjacent mapping is deliberately NOT a spine projection: the readiness WORDING derived from `BindingSourceKind` (replacing the deleted entrypoints dict) maps source kinds to operator-facing nouns, not to actions; it follows the same totality-at-import pattern but lives outside the spine, so the spine's membership stays purely action-classes.

## Rationale

The spine is the smallest structure that gives every surface one vocabulary for next actions while leaving every precise native code intact and every native gate untouched. Totality-at-import is the only enforcement that catches an unmapped new member before it ships silent.

## Consequences

Gains: one what-to-do-next vocabulary for the read-model, CLI and TUI; fact loss closed; one duplicate enum removed. Costs: 5-6 mapping tables to author and maintain - each self-policing. Pitfall: scope creep toward projecting vocabularies no surface reads; the projection set grows only when a surface actually consumes it.
