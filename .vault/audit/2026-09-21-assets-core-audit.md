---
tags:
  - '#audit'
  - '#assets-core'
date: '2026-09-21'
modified: '2026-10-31'
body_schema: 'body-v2'
body_hash: 'sha256:81f941eae8b69c831b2e00bc60c69521821b0d316db74a112be9f3a02c2f0af4'
related:
  - "[[2026-09-21-assets-core-lifecycle-contract-adr]]"
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

## Integrated review, 2026-10-30

Verdict: revision required. Step S14 of the 2026-10-30 plan, over S01 to S13 and S11, S15, S16 as extended. All findings are new with the asset work except the manifest entry. Executed means run against the real domain; every other entry rests on source reading.

### money | high | Removing or redating a baja leaves its zero claim effective and loses the year's deduction
Executed. `_baja_supersessions` in `application/actividad_asset/operations.py`, `uncovered_claim_intervals` in `domain/renta/actividad_asset/claims.py`.

### money | high | Sub-cent basis puts a fully amortized element in permanent conflict
Executed: basis 1234.57 at 35 percent and 50 percent allocation gives 432.0995 against charges of 432.10. `schedule.py` compares unrounded; `history.py` compares at cents.

### never-blocks | high | Incomplete opening history blocks Modelo 100 and 130, even for a withdrawal
`disposal_calculation.py`, `application/aggregation/modelo_bindings_actividad_assets.py`.

### staleness | high | Modelo 130 fingerprint omits accumulated history, so a stale filed figure can pass unseen
`schedule.py` fingerprint against `_constant_percentage_amount`.

### boxes | high | A baja with a non-zero result blocks Modelo 100 with no route to clear it
0179, 0306, 0307, 0385, 0387, 1844, 1846 and 1478 had no bindings; clave 1626 and agrarian excess unestablished.

### never-blocks | high | Second instalments and ancillary rows in amortizable categories block with reclassification as the only remedy
`_validate_primary_purchase` in the ledger lifecycle, `ledger_amortization_row_unregistered`.

### staleness | medium | A new generation or later baja falsely flags consumers, and a disposal-only revision marks claims stale
`ScheduleAuthority.fingerprint`, `_matches_current_schedule` in `register_reads.py`.

### staleness | medium | Filed staleness cost grows with sealed revisions and elements on every status read
`stale_filed_revisions` in `ledger_filing_snapshot.py`. Not measured by the review.

### data-bounds | medium | Years run to 2075, future claims are accepted, and forecast and walk filter claims differently
`register_reads.py`, `operations.py`.

### money | medium | Pre-floor years understate the minimum, the opening span hides claim gaps, and pending display departs from the formula
`disposal_calculation.py`, `domain/renta/actividad_asset/disposal.py`, `register_reads.py`.

### territory | medium | Residence is read from the current profile, so a later move to foral territory blocks earlier periods
`_territory_refusal` in `modelo_bindings_actividad_assets.py`.

### manifest | medium | A stale contract manifest kills the worker and surfaces as custody_recovering
Pre-existing. `contract_manifest.py`, `worker_operation_requests.py`. The manifest check is in no packaging or merge recipe.

### mcp | medium | No asset refusal is run through the MCP server
`test_refusal_reaches_frontends.py` covers MCP at schema level only.

### replay | medium | An identical retry of dispose or create is refused where record_claim replays
`operations.py`.

### tests | medium | Test support diverges from production and some tests prove little
`register_support.py` disposal bounds, `test_opening_coverage.py`, and `test_ledger_income_chain_aeat_exempt_worked_example.py`, which types 0208 by hand and is no amortization oracle.

### decision | low | later_affectation_on is justified by LIRPF art. 28.3 but unnamed in the disposal ADR
Named by amendment on 2026-10-30.

### law | low | The RIS art. 4.3 group paragraph is unresolved for an individual buyer
Letter a could over-deduct if it applies; no fact records the seller relationship. Under research.

## Tax literals outside the asset code, 2026-10-30

Read-only sweep of `domain/` and `application/`, using the classifier in `dev/quality/tests/test_activity_asset_tax_literals.py` over 1,894 files. About 85 percent of 2,120 findings were technical. Letter claves were only grepped, and 65 `domain/calculations/registry` files were sampled.

### registry-owned-facts | high | Tax facts remain in code outside the asset code
Pre-existing, and against the operator's rule of 2026-10-30. Families: a threshold duplicating the registry at `application/modelo/dt12_advisory.py:28`; box lists at `application/modelo/projection.py:80`, `application/calculations/m303_regimen_simplificado_annual_summary.py:56`, `domain/calculations/registry/ledger_renta_income_bindings.py:146`; claves at `application/filing/export_producer.py:1022`, `domain/foreign_assets/register.py:94`, `domain/contribuyente/renta_codes.py:36`, `application/wizard/command_parameters.py:90`, `domain/calculations/registry/withholding_bindings.py:279`, `application/filing/producer_snapshot_m360.py:68`; modelo routing at `application/aggregation/withholding_filing_cadence.py:43`, `domain/calculations/registry/applicability.py:379`, `domain/deadlines/festivos.py:243`; layout offsets at `application/filing/m190_context_validation.py:17`, `application/filing/m280_context_validation.py:17`; period rules at `domain/period.py:66`, `domain/renta/maritime_exemption.py:67`.

### registry-owned-facts | medium | The literal gate cannot see every form of a fact
`Field(ge=, le=)` bounds hide claves, modelo ids look like box ids, and letter claves aren't detected.

## Integrated re-review, 2026-10-30

Verdict: revision required, no critical findings. Findings from the first review are resolved except where repeated here. Installed journeys and real CLI and TUI launches did not run. The MCP refusal entry reported as open is closed by `dev/mcp_eval/tests/test_asset_refusal_through_mcp.py`, which the review did not look in.

### head-integrity | high | HEAD could not import the asset subsystem
`disposal.py:453` had a syntax error, with consumers importing names from a split module left uncommitted. Repaired in `04ae81174d`.

### never-blocks | high | An unowned amortizable row with no base or in foreign currency blocks Modelo 130
`modelo_bindings_renta_expenses.py:570`. Executed.

### staleness | high | A late claim for an earlier year changes the baja result with no drift
Executed: box 1654 moves from 897.53 to 1,200.00 with equal consumption. `disposal_calculation.py:115`.

### visibility | high | Non-durable findings disappear at reopen, and the form never shows their specifics
`calculation_bucket_actions.py:742`, `work_form_issue_lines.py:389`. Decision: persist them with the calculation revision.

### never-blocks | high | Any amortization note replaces Verify with Fill
Executed. `work_form_next_step.py:269`.

### tests | high | Three work-form gate parametrizations fail
`test_work_form_gate_agreement.py:174`, the same inconsistency.

### baja-correction | medium | Omitting disposal silently removes a baja
`operation_dtos.py:392`. Executed.

### refusal-rendering | medium | Plan refusal keys travel without their facts
`operations.py:806`.

### identical-flagged | medium | A correction to evidence alone marks every claim stale
`lifecycle.py:469`. Executed.

### tests | medium | Register test support departs from production
`register_support.py`.

### claim-replay | low | A fresh forecast under a new generation reads as a conflict
`claims.py:97`. No dead end.

### boxes | low | Several sales in one year collapse into one row
`actividad_asset_disposal_bindings.py:139`.

### outside-ledger | low | The remedy for a later row on an outside-ledger element cannot be carried out
`revision_validation.py:58`.

### m131 | low | An uncalculable excess says nothing on Modelo 131
`modelo_bindings_actividad_assets.py:630`.

## Modelo 184 clave A reduction

### Reduction citation | info | The block on clave A lifted once the design's citation was explained as a stale renumbering

The socio record of the Modelo 184 design cites LIRPF art. 24.2, which does not fit Ley 35/2006, whose art. 24 has no apartado 2. RDLeg 3/2004 art. 24 (BOE-A-2004-4347) is the old number: its apartado 2 reduced income of more than two years' generation. The current rule is LIRPF art. 26.2, reducing the net income of art. 25.4, which is the socio record's clave A subclave 02. The entity record of the same design cites art. 26.2 itself. `2026-08-26-tui-architecture-m184-socio-clave-subclave-row-shape-adr` allowed the block to lift on this explanation. The fact key `reduccion.bearing` now reads `A:02,C,D`; clave A without 02 and clave E refuse. No filing-grade example has confirmed the reading.
