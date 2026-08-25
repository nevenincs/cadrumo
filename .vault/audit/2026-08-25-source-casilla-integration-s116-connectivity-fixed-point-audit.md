---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:f72dbef589abbab7465e9c97838eef2c62cfc02db2b3868f7edd298479d52987'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - '[[2026-08-22-source-casilla-integration-W06-P20-S116]]'
---
# `source-casilla-integration` audit: `S116 source-connectivity fixed-point execution evidence`

## Scope

Execution and review evidence for `W06.P20.S116` at the current tree after the completed source slices and public-module relocations. Scope includes the structural discovery boundary, census locator/digest maintenance, and the inventory readiness truth correction. It does not promote a source candidate or claim filing readiness.

## Findings

### s116-two-pass-locator-drift | high | Two fresh processes find the same absent inventory locator

Two independently launched fresh discovery probes each found 464 capabilities with the identical sorted-ID digest `sha256:0be7d9fae88abef85b83af8eddd87a1cc4a030c8e6e751587c6f6ae42975cf64`. Their ID sets were equal.

Each following fresh `uv run --no-sync python -m dev.source_connectivity.cli compare` invocation exited 1 with precisely the same refusal: `source-connectivity census mismatch: census capability locator line is absent: inventory.stock-valuation: src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py:4866`.

The earlier `rows.related-party-operation` line drift was repaired and no longer refuses comparison. The current census still attests a CLI command-spec location removed by concurrent command-surface relocation. Because canonical comparison refuses before it can produce a validated assignment/membership projection, this step cannot prove that no candidate is unclassified or unactioned. The two-pass condition is therefore not satisfied and `S116` remains open.

### s116-static-inventory-posture | medium | The manifest has 15 recorded rows and no expired dated deferral, but its assignment is not currently valid

A read-only manifest inventory reports 15 rows: `censo.modelo-036-profile-status` is `manual_by_design`; `inventory.stock-valuation` and `assets.amortization-ledger` are `connect_candidate`; `assets.capital-register` and `fincas.annual-aggregates` are `grounding_blocked`; `rows.related-party-operation`, `rows.refund-operation`, `rows.donativo-donor`, and `rows.gasto193-contributor` are `ingress_blocked`; `rows.withholding296` is `registry_blocked`; the two remaining calculation/ingress selectors are `not_applicable`; and the remaining row-assembler, secure-repository, and source-ownership selectors are `duplicate_or_stale`.

All seven entries with `expires_on` are current through 2026-12-31. That static expiry observation is not a substitute for a successful canonical assignment: there is no valid candidate/disposition membership set, count, or equality proof while the locator drift is outstanding.

### s116-locator-drift-resolved | pass | Every reviewed locator re-fetches after proven relocations

The inventory command declarations resolve to the split inventory command-spec modules, and the row-assembler locators resolve to their current typed dispatch branches. Discovery independently returns each updated locator for the capability it claims. No replacement capability, candidate, disposition, or source owner was invented.

### s116-public-definition-discovery | pass | Public modules remain visible without facade redeclaration

The private-to-public cutover moved fourteen calculation-helper definitions one-for-one. The reviewed helper cardinality remains 267. Discovery now treats a non-private definition module as a public surface while excluding colocated `conftest.py`; a mutation test proves both directions. The resulting digest is `sha256:cf1081c06fe140c568dd58e6b14bc970ce1929f6c7d3639b39d61e519bd60a18`. This preserves capability identity at its defining module and does not recreate an inert package facade.

### s116-secure-port-discovery | pass | Workflow custody remains visible behind its typed secure-store port

The public workflow repositories still persist through `WorkflowSecureObjectStorePort`; their disappearance was a scanner blind spot, not a repository retirement. A generic typed-port detector and mutation proof retain both repositories. The only net-new secure repository is the encrypted filing-export replay custody adapter, classified in the existing operational remainder without a calculation-source claim.

### s116-inventory-truth | pass | Readiness names only the remaining filing boundary

The inventory readiness fact no longer restates already-completed resolver, mesh, binding, orchestration, identity, and override-refusal work as missing. It remains false for the actual open boundary: grounded repeated M100 activity-row casilla materialization, official rendering, and end-to-end verification without fabricated activity-envelope facts. The census retains `connect_candidate`.

### s116-two-pass-fixed-point | pass | Two fresh comparisons produce the same complete assignment

Two separate fresh processes each return `status = match`, 478 discovered capabilities, 478 assignments, and 15 census rows. No capability is unclassified or unactioned. All seven dated deferrals remain current through 2026-12-31, and no row is promoted to `connected`.

### s116-review-secure-port-proof | pass | False secure-repository classification is mutation-guarded

The first independent review rejected a detector that trusted any class-body secure-port-shaped name; the second rejected constructor annotation alone. The final detector requires the typed constructor argument to bind a repository attribute and requires that bound attribute to participate in an operational method call. Negative mutations prove both an unrelated class-body marker and an unused bogus constructor port cannot classify plaintext persistence as secure. Optional union-typed workflow store ports remain visible because their bound `_objects` attribute participates in persistence calls.

### s116-review-public-route | pass | Ownership discovery consumes one public defining module

The independent review found the source-ownership discovery import crossed into the private calculation-route module. The authority was hard-renamed to the public `application.modelo.calculation_route` defining module and every scoped production, test, discovery, and census consumer moved atomically. The legacy module is absent; no compatibility facade or duplicate authority was introduced.

### s116-current-registry-gate | pass | Obligatory blank positions require emitted filler bytes

During re-review a newer export-coverage gate exposed M126 and M128 position 12. Both layouts already emit the official one-byte filler, while their extracted design rows carry the terminal sentence `En blanco` in the description rather than the content field. Bounded terminal-sentence recognition preserves the obligatory position and credits only filler bytes; the focused mutation test proves the position cannot disappear or accept taxpayer data.

### s116-independent-re-review | pass | No critical, high, or medium finding remains

The independent reviewer rejected two progressively weaker secure-port detectors and re-read the final tree after both remediations. The final verdict is PASS: the exact plaintext-marker counterexample refuses, both workflow repositories remain correctly discovered, private helper paths remain excluded, the public calculation-route move has no legacy module or scoped reference, and obligatory-blank handling stays narrowly filler-bound.

## Recommendations

- Close `S116` after the focused source-connectivity suite and Vaultspec checks pass.
- Keep `S117` open until its dedicated campaign-close test proves no expired deferral, unexplained disappearance, or unsupported connected claim. Do not treat the S116 fixed point as registry filing readiness.

## Verification receipt

- Historical pre-repair passes: 464 capabilities; both refused the obsolete inventory command-spec locator as recorded above.
- Final comparison pass 1: exit 0; 478 capabilities; 478 assignments; 15 rows; `status = match`.
- Final comparison pass 2: exit 0; identical counts and `status = match`.
- Focused discovery tests: 13 passed.
- Inventory readiness test: 1 passed.
- Full source-connectivity suite: 63 passed.
- Public calculation-route suite: 27 passed.
- Binding-source mesh parity suite: 12 passed.
- Scoped legacy-route scan: the retired application private module is absent and no application, domain, or development consumer references it.
- Ruff over source-connectivity and inventory readiness surfaces: passed.
- Feature-scoped Vaultspec check: passed.
