---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:b7e6daf8ffd2b00f2e53da9ea758a25f6f0c67313ed61100ee855387b009d085'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - '[[2026-08-22-source-casilla-integration-W06-P20-S116]]'
---
# `source-casilla-integration` audit: `S116 source-connectivity fixed-point execution evidence`

## Scope

Execution evidence for `W06.P20.S116` at the current tree after the completed source slices. The scope is the canonical structural discovery and census-assignment boundary only. It does not change census entries, registry dispositions, runtime, the source plan, or the generated feature index.

## Findings

### s116-two-pass-locator-drift | high | Two fresh processes find the same stale related-party locator

Two independently launched `uv run --no-sync python -m dev.source_connectivity.cli generate` probes each discovered 476 capabilities with the identical sorted-ID digest `sha256:b48f226826e09ff58aabe9b4eb2b3dae7af8544ef7f3995b62e4002cc8988e03`. Their ID sets were equal.

Each following fresh `uv run --no-sync python -m dev.source_connectivity.cli compare` invocation exited 1 with precisely the same refusal: `source-connectivity census mismatch: census capability locator drift for rows.related-party-operation: row_assembler:per_related_party_operation now resolves to 'src/cadrumo/application/calculations/_row_set_assembly.py:170'`.

The current census still attests locator line 168 for that capability. Because canonical comparison refuses before it can produce a validated assignment/membership projection, this step cannot prove that no candidate is unclassified or unactioned. The two-pass condition is therefore not satisfied and `S116` remains open.

### s116-static-inventory-posture | medium | The manifest has 15 recorded rows and no expired dated deferral, but its assignment is not currently valid

A read-only manifest inventory reports 15 rows: `censo.modelo-036-profile-status` is `manual_by_design`; `inventory.stock-valuation` and `assets.amortization-ledger` are `connect_candidate`; `assets.capital-register` and `fincas.annual-aggregates` are `grounding_blocked`; `rows.related-party-operation`, `rows.refund-operation`, `rows.donativo-donor`, and `rows.gasto193-contributor` are `ingress_blocked`; `rows.withholding296` is `registry_blocked`; the two remaining calculation/ingress selectors are `not_applicable`; and the remaining row-assembler, secure-repository, and source-ownership selectors are `duplicate_or_stale`.

All seven entries with `expires_on` are current through 2026-12-31. That static expiry observation is not a substitute for a successful canonical assignment: there is no valid candidate/disposition membership set, count, or equality proof while the locator drift is outstanding.

## Recommendations

- Assign a distinct mechanical locator-maintenance step to update only the `rows.related-party-operation` locator after mutation-backed proof identifies the canonical live location. It must neither revise the candidate's `ingress_blocked` disposition nor alter any other census decision.
- Rerun two separate fresh generate-and-compare passes after that correction. Close `S116` only if both comparisons emit validated, identical assignment sets with no unclassified or unactioned candidate and no expired governed deferral.

## Verification receipt

- `uv run --no-sync python -m dev.source_connectivity.cli generate` (pass 1): exit 0; 476 capabilities; digest above.
- `uv run --no-sync python -m dev.source_connectivity.cli compare` (pass 1): exit 1; exact locator-drift refusal above.
- `uv run --no-sync python -m dev.source_connectivity.cli generate` (pass 2): exit 0; 476 capabilities; same digest and ID set.
- `uv run --no-sync python -m dev.source_connectivity.cli compare` (pass 2): exit 1; byte-identical locator-drift refusal.
- The broadening focused pytest run was stopped on direction once the canonical two-pass failure was conclusive; its partial dots are deliberately not claimed as a passing receipt.
