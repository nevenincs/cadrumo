---
tags:
  - '#audit'
  - '#assets-core'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:c8170c6a668e8fcea03ebe90f7073456641d6a1273079cc06a22026eef284d7f'
related:
  - "[[2026-09-21-assets-core-plan]]"
  - "[[2026-09-21-assets-core-lifecycle-contract-adr]]"
---

# `assets-core` audit: `Integrated assets-core review`

## Scope

Reviewed Phase P01 across the accepted lifecycle decision, its code/reference
grounding, the current amortization-routing regression, inventory separation,
execution evidence, and the transition into the persisted schedule work. Source
commits reviewed: `d50d31373a`, `33b7c8492d`, and `376669fb66`.

Reviewed Phase P02 across the accepted lifecycle and cost-basis decisions, the
typed asset/revision/claim contracts, 2025 normal and simplified authority
tables, deterministic day-count schedule, encrypted CAS-guarded persistence,
restart reconstruction, and focused verification evidence.

Reviewed Phase P03 across exact-key authority resolution, mandatory encrypted
history wiring, the live Modelo 100 and Modelo 130 source mesh, scoped
acquisition-cost collisions, and claim provenance.

Reviewed P04 reciprocal IVA linkage and the completed P05 shared application,
CLI, and TUI adapters. The installed-process and validated-export acceptance
work remains open and is not included in the passing scope.

## Findings

### phase-01 | low | unsafe full-cost routing remains intentionally pinned

The regression correctly proves that an unscheduled acquisition still reaches
casilla 0208 at full base. This is evidence for the P03 collision fix, not a
supported outcome. The accepted atomic-delivery boundary prevents the future
asset persistence or API from being presented as complete until resolver and
filing ownership land with it.

Result: PASS. No critical or high findings.

### phase-02 | low | shared namespace-order tripwire has a concurrent omission

The assets namespace declaration, enrollment, and expected-order entry agree.
The global expected-order test continues to fail later in the sequence because
the concurrently added `withholding_workflow` namespace is absent from that
test's expected tuple. Assets work must not patch the income lane's ownership
gap; the focused assets persistence, registry-adoption, grammar, and encryption
checks pass.

Result: PASS. No critical or high findings. The unrelated shared-test failure is
recorded as an integration dependency rather than hidden or overwritten.

### phase-03 | low | non-linear and special intangible methods remain explicit refusals

The live resolver supports the enrolled 2025 normal and simplified linear-table
classes, including their software destinations. The separately authored
non-estimable-life and goodwill limits are not silently selected, and unsupported
methods or class keys refuse. This is an explicit support boundary, not an
under-declared zero.

Result: PASS. No critical or high findings. Live regression evidence proves the
scheduled EUR 500 charge, additive M130 ownership, distinct M100 destinations,
and refusal of the competing EUR 2,000 acquisition-cost route.

### phase-04-05 | medium | frontend parity is implemented but installed acceptance is incomplete

CLI and TUI delegate creation, inspection, correction, forecast, and explicit
claim recording to the same application operations. Registry selection is
pinned outside the frontends and neither adapter performs depreciation
arithmetic. The installed wheel built and imported from site-packages, but the
isolated TUI child did not produce a terminal result. The shared exporter is
also still under another lane's active ownership.

Result: PASS for P04.S07, P05.S09, and P05.S10. P04.S08, P05.S11, and P05.S12
remain open. AS3, AS4, AS5, AS6, AS8, and AS10 are proven; AS1, AS2, AS7, AS9,
AS11, and AS12 are blocked. No installed journey or official export is claimed.

## Recommendations

Retain the regression unchanged through P02. In P03, add the positive scheduled
charge and scoped competing-claim refusal before replacing the unsafe behavior.
Do not weaken the test to make an intermediate backend slice appear complete.

For P03, resolve authority rows through the registry-backed provider rather
than accepting a caller-invented rate, preserve the single M130 casilla-02
owner, and displace the proven unsafe transaction-ledger 0208 route only within
the scoped acquisition/depreciation collision.
