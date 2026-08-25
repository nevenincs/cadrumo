---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:583ce1764a47b72c056ff39ee52937298b08a92ee8588a7a9168002c701744b4'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - '[[2026-08-22-source-casilla-integration-W06-P20-S116]]'
---
# `source-casilla-integration` audit: `S116 source-connectivity fixed-point execution evidence`

## Scope

Execution evidence for `W06.P20.S116` at the current tree after the completed source slices. The scope is the canonical structural discovery and census-assignment boundary only. It does not change census entries, registry dispositions, runtime, the source plan, or the generated feature index.

## Findings

### s116-two-pass-locator-drift | high | Two fresh processes find the same absent inventory locator

Two independently launched fresh discovery probes each found 464 capabilities with the identical sorted-ID digest `sha256:0be7d9fae88abef85b83af8eddd87a1cc4a030c8e6e751587c6f6ae42975cf64`. Their ID sets were equal.

Each following fresh `uv run --no-sync python -m dev.source_connectivity.cli compare` invocation exited 1 with precisely the same refusal: `source-connectivity census mismatch: census capability locator line is absent: inventory.stock-valuation: src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py:4866`.

The earlier `rows.related-party-operation` line drift was repaired and no longer refuses comparison. The current census still attests a CLI command-spec location removed by concurrent command-surface relocation. Because canonical comparison refuses before it can produce a validated assignment/membership projection, this step cannot prove that no candidate is unclassified or unactioned. The two-pass condition is therefore not satisfied and `S116` remains open.

### s116-static-inventory-posture | medium | The manifest has 15 recorded rows and no expired dated deferral, but its assignment is not currently valid

A read-only manifest inventory reports 15 rows: `censo.modelo-036-profile-status` is `manual_by_design`; `inventory.stock-valuation` and `assets.amortization-ledger` are `connect_candidate`; `assets.capital-register` and `fincas.annual-aggregates` are `grounding_blocked`; `rows.related-party-operation`, `rows.refund-operation`, `rows.donativo-donor`, and `rows.gasto193-contributor` are `ingress_blocked`; `rows.withholding296` is `registry_blocked`; the two remaining calculation/ingress selectors are `not_applicable`; and the remaining row-assembler, secure-repository, and source-ownership selectors are `duplicate_or_stale`.

All seven entries with `expires_on` are current through 2026-12-31. That static expiry observation is not a substitute for a successful canonical assignment: there is no valid candidate/disposition membership set, count, or equality proof while the locator drift is outstanding.

## Recommendations

- Assign a distinct mechanical locator-maintenance step to determine whether `inventory.stock-valuation` has a relocated live command-spec capability or has disappeared from discovery. Update only a proven live locator, or route candidate retirement through its owning census decision; never invent a replacement line or revise its disposition merely to make comparison pass.
- Rerun two separate fresh generate-and-compare passes after that correction. Close `S116` only if both comparisons emit validated, identical assignment sets with no unclassified or unactioned candidate and no expired governed deferral.

## Verification receipt

- Fresh discovery pass 1: exit 0; 464 capabilities; digest above.
- Fresh comparison pass 1: exit 1; exact absent-locator refusal above.
- Fresh discovery pass 2: exit 0; 464 capabilities; same digest and ID set.
- Fresh comparison pass 2: exit 1; byte-identical absent-locator refusal.
