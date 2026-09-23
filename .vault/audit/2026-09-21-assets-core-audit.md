---
tags:
  - '#audit'
  - '#assets-core'
date: '2026-09-21'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:e454ef892a81e7847bf288a278b90910177397152cda24dc8cc27ffbb8acd0f4'
related:
  - "[[2026-09-21-assets-core-plan]]"
  - "[[2026-09-21-assets-core-lifecycle-contract-adr]]"
  - '[[2026-09-23-assets-core-plan]]'
  - '[[2026-09-23-assets-core-amortization-method-set-adr]]'
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
remain open. This review point preceded the AS7 implementation recorded below.
No installed asset journey or official export is claimed.

### phase-05-as7 | low | free-depreciation authority and cap are adopted

The existing published 2025 authority now resolves an explicit low-value
election for eligible new material assets, enforces the EUR 300 unit threshold
and taxpayer-period EUR 25,000 cap, and rechecks profile-wide effective claims
inside the encrypted CAS mutation. Forecasts do not consume the cap, retries do
not consume it twice, corrections replace effective consumption, and competing
concurrent claims cannot oversubscribe it.

Result: PASS. AS7 is proven through the real registry resolver, application
operation, encrypted claim history, and idempotent claim path.

### phase-05-installed | medium | staged runner exposes a profile-admission dependency

The earlier no-output child did not retain enough evidence to establish a
product hang. The replacement supervisor records command identity, PID,
installed origin, isolation roots, stage receipts, timeout status, and cleanup.
Installed probe and Home journeys exit successfully. Ledger admission exits 2
after mounting the public `FieldEditScreen`; no asset interaction occurs.

Result: P05.S11 remains open. AS1, AS2, and AS11 remain blocked. The required
bounded Luna route trace could not be dispatched because the agent thread limit
was exhausted; no substitute model or private-screen automation was used.

### phase-04-export | medium | IVA evidence is substantial but public filing evidence is missing

Reserved evidence passes for initial IVA deduction, reciprocal acquisition,
regularization, missing facts, disposal, and bucket-bound export behavior. The
live source-mesh integration currently fails because its fixture does not meet
the newly required taxpayer-profile readiness contract. A complete installed
M303 export is additionally blocked before serialization by the missing public
typed `FilingInstanceEvidence` authoring/resolution operation.

Result: AS9 and AS12 remain blocked on these exact owner contracts. No exporter
repair is inferred and no official filing artifact is claimed.

### final-integrated-acceptance | low | installed parity and filing artifacts close the remaining scope

The repaired profile and IVA fixtures now use canonical readiness facts and
retain negative incomplete-profile refusal. The current published authority
still resolves the 2025 linear and low-value asset branches. Installed TUI
journeys complete creation, immutable-revision inspection, correction, forecast,
first claim, idempotent replay, non-consuming filing handoff, restart readback,
and both CLI/TUI continuation directions without timeout or forced cleanup.

The installed filing journey independently overlays one EUR 300 asset claim on
the established EUR 2,400 expense control. Modelo 130 reports EUR 2,700 total
expenses; Modelo 100 reports the same claim in its material-amortization
destination and zero intangible amortization. This is destination composition,
not a second basis consumption. The exported Modelo 100 XML passes the pinned
official 2025 XSD. The public filing-evidence operation remains scoped to M303;
IRPF export does not acquire an unrelated exonerado-390 dependency.

Result: PASS. P04.S08 and P05.S11 are complete, and the final integrated review
found no critical or high findings. AS1-AS12 are supported by their recorded
domain, application, installed frontend, IVA source-mesh, and export evidence.

### method-set-review | high | used doubling reached intangibles and claims skipped the new invariants

The method-set plan was reviewed across commits `231bee9648` through `d30450a7cd`
against its accepted decision and the bundled RIS, LIS and RIRPF texts, with two
high findings. The used-asset multiplier applied to intangibles, although RIS
art. 4.3 covers material assets only: a used software licence with a 3,000 basis
was charged 1,980 instead of 990. The claim path stored a caller-held forecast
after checking only interval overlap and the low-value cap, so two forecasts
taken before recording could together claim twice an R&D machine's basis. Lower
findings: modality gating for the used and multi-shift multipliers sat in Python;
the constant-percentage final year could strand a cent; a simplified used
building demanded a construction date; two receipt fields were asserted rather
than measured; a new inline lint suppression; class and kind admission read a
string prefix. The review confirmed every hand oracle, bracket, weighting and
refusal citation.

Result: REVISION REQUIRED. Every finding was fixed in `33129301ba` and
`b630c0e93e`; the asset errors were rooted in the registered hierarchy in
`58523f3fa7`.

### method-set-re-review | medium | a superseding claim could never be forecast

The re-review of `33129301ba` through `30d35de000` verified every earlier
finding fixed, with the used multiplier keyed `normal:material` in the registry
and each new claim recomputed at record time and rechecked inside the encrypted
compare-and-swap. It found that the public forecast always counted the claim a
correction would replace, so a correction near the basis cap could never match
its recomputed forecast, and that the history write did not recheck the claim's
revision was still current.

Result: APPROVED with the two findings fixed in `f92721ce93`: forecast accepts
the superseded claim through operations, CLI and TUI, and the history write
refuses a new claim under a superseded revision. `2f97378e51` exposes each
revision's identity in CLI inspection and adds a superseding-claim step to the
TUI screen test and the installed CLI journey. The installed proof at
`0d34b1534a` (wheel `16d5e13e`, authority generation `cadc37df`, store format
`cadrumo-authority-sqlite-v2`) proved the constant-percentage lifecycle through
installed CLI and TUI, M130, M100 and the pinned 2025 XSD; it predates the
supersession fixes, which await the next installed run.

## Recommendations

Retain the regression unchanged through P02. In P03, add the positive scheduled
charge and scoped competing-claim refusal before replacing the unsafe behavior.
Do not weaken the test to make an intermediate backend slice appear complete.

For P03, resolve authority rows through the registry-backed provider rather
than accepting a caller-invented rate, preserve the single M130 casilla-02
owner, and displace the proven unsafe transaction-ledger 0208 route only within
the scoped acquisition/depreciation collision.
