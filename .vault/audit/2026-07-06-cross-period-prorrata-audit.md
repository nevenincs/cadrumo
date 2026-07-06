---
tags:
  - '#audit'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
  - "[[2026-07-06-cross-period-prorrata-W02-P03-S10]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace cross-period-prorrata with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `cross-period-prorrata` audit: `S10-S18 seed/override review`

## Scope

Reviewed the `W02.P03.S10` through `W02.P04.S18` seed/override implementation and vault
closure artifacts: the carried-prior-definitive seed helper, the evaluation
surface for blocking/advisory findings, source-observation identity recording on
the carried entry, the committed real-observation seed tests, the legacy
field-absent observation compatibility needed to exercise the missing-stamp
advisory, the AEAT-authorised and inicio-de-actividades override recording
services, the application in-force lookup that delegates to the single domain
precedence ladder, the prior-observation cross-check findings, and the committed
override/cross-check tests. The review also checked the
S10/S11/S12/S13/S14/S15/S16/S17/S18 exec records, the plan checkbox mutations
performed by the vault CLI, and the rebuilt feature index. The review checked
intent alignment with the accepted prorrata ADR, the period-revision carry rule,
the existing anti-tautology null-refusal proof, and the plan boundary that leaves
in-year apportionment to the next wave.

## Findings

No open findings.

## Recommendations

- Continue with `W03.P05.S19` for provisional apportionment in the shared aggregation path.
- Do not treat this narrow seed review as the campaign close honesty audit.

## S19 Review

Reviewed the `W03.P05.S19` implementation in the shared IVA ledger aggregation
path. The diff adds an internal `IvaLedgerProrrataApportionment` carrier, loads
the whole-entity active general register entry for the filing year, resolves the
already-declared domain precedence ladder, and applies the resulting percentage
only after `ledger_iva_aggregation` selector resolution. The binding-value
postprocess derives its target set from revision casillas whose section includes
`deducible` and whose binding selector fact is `iva_amount_sum`, so base bindings
and devengado reverse-charge bindings stay unapportioned while deducible reverse
charge and soportado/import cuota bindings are reduced. No new binding source
kind, resolver convention, validator convention, or registry selector shape was
introduced.

Findings: no open S19 implementation findings.

Residual gate inventory: `ruff check` is clean for the touched aggregation files,
and the local IVA aggregation subset that does not load the full registry passed.
The broader registry-backed IVA tests currently fail before reaching this code on
unrelated Modelo 714 registry validation diagnostics.

## S20 Review

Reviewed the `W03.P05.S20` implementation around the IVA source-mesh resolver
and the prorrata apportionment carrier. The diff keeps the already-approved
`ledger_iva_aggregation` source kind, preserves the register's applied
percentage, regulated provisional provenance, and carried source-observation
identity on the apportionment DTO, and emits those facts through the existing
`CalculationSourceProvenance` channel. The resolver row also carries the
registry legal/source grounding for the deducible cuota casillas it qualifies,
while the actual casilla observation trail remains the existing
`CasillaObservation` surface produced by the registry engine. No new binding
source kind, resolver convention, validator convention, or registry selector
shape was introduced.

Findings: no open S20 implementation findings.

Residual gate inventory: `ruff check` is clean for the touched implementation
and resolver-test files. The targeted prorrata provenance resolver regression,
the full ledger source-mesh resolver test file, and the IVA ledger aggregation
test file all pass sequentially.

## S21 Review

Reviewed the `W03.P05.S21` regression. The new test records a fully taxable
domestic purchase in the real encrypted transaction repository, captures the
shared IVA ledger aggregation and canonical binding payload before any prorrata
register exists, then records a `ninguna` prorrata-register entry for the same
ejercicio and re-runs the same repository-backed path. It asserts byte-identical
aggregation JSON and binding payload bytes across the two runs, so the no-prorrata
regime preserves the previous full-deduction behavior without a hand-computed
cuota oracle. No production code or source taxonomy changed.

Findings: no open S21 implementation findings.

Residual gate inventory: `ruff check` is clean for the new regression file, and
the new regression passes sequentially.

## S22 Review

Reviewed the `W03.P05.S22` field-flow regression. The new test records a real
repository-backed sale and purchase, captures the shared IVA ledger binding
values before any prorrata register exists, then records an active `general`
entry with a carried prior definitive provisional percentage and re-runs the
same aggregation path. The assertions prove the active apportionment carrier is
present, the deducible cuota binding is lower than the baseline value, the
matching deducible base binding stays equal to baseline, and an output IVA cuota
binding stays equal to baseline. The test therefore proves the provisional
percentage bites on the intended field flow without hand-computing the expected
reduced cuota or introducing a parallel formula.

Findings: no open S22 implementation findings.

Residual gate inventory: `ruff check` is clean for the prorrata apportionment
regression file, and the full file passes sequentially.

## S23 Review

Reviewed the `W03.P05.S23` parity regression. The new test records real M303
ledger rows, an active prorrata-general register entry, and an IVA-wallet zero
decision in the encrypted runtime profile, then compares two paths over the same
registry revision: the live bucket-aggregation calculate mesh and the direct
`LedgerIvaAggregationSourceResolver` plus `calculate_registry_snapshot` pull
shape used by the existing parity module. It asserts the apportioned deducible
cuota binding is positive and below the source purchase cuota, the persisted
live binding override equals the resolver value, the semantic deducible casilla
equals that apportioned binding, and official box `29` matches on both paths.
No new source kind, resolver convention, or hand-computed prorrata oracle was
introduced.

Findings: no open S23 implementation findings.

Residual gate inventory: `ruff check` is clean for the parity regression file,
the targeted S23 regression passes sequentially, and the full parity file passes
sequentially.

## S24 Review

Reviewed the `W04.P06.S24` settlement projection change after re-grounding the
step against the cross-period prorrata ADR, the scope ADR, and the current
registry/advisory code. The diff keeps `PRORRATA_REGULARIZACION` deferred and
does not touch `_source_mesh.py`, registry source kinds, resolver conventions,
validator conventions, or registry selector shapes. The new
`ProrrataRegularizacionFeedProjection` is a structured wrapper over the existing
`compute_regularizacion_prorrata_anual` result, exposing the same proposed value
for Modelo 303 casilla 44 and the Modelo 390 annual regularización field while
leaving the definitive percentage under registry-declared annual-volume
authority.

Findings: no open S24 implementation findings.

Residual gate inventory: `ruff check` is clean for the touched calculation
projection, facade, and test files, and the prorrata regularización calculation
test file plus the model-level advisory regression pass sequentially.

## S25 Review

Reviewed the `W04.P06.S25` ledger-rollup divergence projection after re-grounding
the step against the cross-period prorrata ADR, the W04 plan row, the current
`Period.contains` boundary authority, and the existing prorrata calculate-path
advisory collector. The diff keeps declared annual prorrata volume casillas as
the authority and adds only a pure calculation helper over existing
`IvaLedgerObservation` rows. It classifies in-ejercicio repercutido output
volume into con-derecho and sin-derecho buckets, treats Art. 20.Uno.26 exempt
output as con-derecho and other domestic exempt output as sin-derecho, excludes
input-side rows and out-of-window rows, and returns a non-blocking
`CalculationSourceDiagnostic` when the ledger rollup contradicts the declared
values.

Findings: no open S25 implementation findings.

Residual gate inventory: `ruff check` is clean for the touched calculation
projection, facade, and test files. The prorrata regularización calculation test
file passes sequentially with 7 tests, and the model-level advisory regression
passes sequentially with 5 tests. The combined focused slice passes sequentially
with 12 tests.

## S26 Review

Reviewed the `W04.P06.S26` settlement persistence change after re-grounding the
step against the cross-period prorrata ADR, the W04 plan row, the existing
participation-index co-emission pattern, and the current prorrata-register
payload contract. The diff keeps M303 settlement casillas under their existing
registry ids, adds no binding source kind, resolver convention, validator
convention, or registry selector shape, and routes the register update through
the existing filing secure-object transaction. The register adapter exposes a
`to_secure_object_write` helper while preserving its direct JSON payload format,
so existing save/load and corrupt-payload roundtrip proofs remain valid.

The filing path now recognizes only M303 `4T` and `0A` revisions that carry all
three definitive prorrata settlement values: total volume,
con-derecho volume, and definitive percentage. It writes those values back to the
whole-entity register entry, derives sin-derecho volume as total minus
con-derecho, preserves existing regime/provisional provenance/source-observation
facts, retains sector entries, and creates a minimal whole-entity entry when no
current-year row exists. Invalid negative sin-derecho volume is left to the
domain model validation rather than being silently accepted.

Findings: no open S26 implementation findings.

Residual gate inventory: `ruff check` is clean for the touched persistence,
filing, and test files. The new prorrata settlement write-back test file passes
sequentially with 3 tests, the prorrata register roundtrip file passes
sequentially with 4 tests, and the existing participation co-emission regression
passes sequentially with 1 test.

## S27 Review

Reviewed the `W04.P06.S27` regression slice after re-grounding it against the
W04 plan row and the current S24-S26 implementation. The change is test-only and
does not alter binding source kinds, resolver conventions, validator
conventions, registry selectors, or production write paths. The projection test
now names the supplied definitive percentage as the declared annual-volume value
and asserts that value is the one projected to Modelo 303 casilla 44 and the
Modelo 390 annual field. The existing ledger contradiction test remains a
declared-authority proof: the rollup can fire a non-blocking diagnostic, but it
does not replace the declared annual volume casillas.

The new integration test uses real encrypted repositories and registry-grounded
M303 settlement observations. It files a verified 2026 4T M303 revision through
the production filing persistence helper with both the prorrata register
repository and the calculation-observation repository supplied. The assertions
prove the settlement register entry receives definitive percentage and volume
inputs, and the stamped local filed observation lets
`evaluate_carried_prior_definitiva_seed` produce the 2027
`carried_prior_definitiva` entry with percentage `75` and source observation
identity `303:2026:4T`.

Findings: no open S27 implementation findings.

Residual gate inventory: `ruff check` is clean for the touched test file. The
prorrata regularización test file passes sequentially with 8 tests, the seed
test file passes sequentially with 3 tests, and the settlement write-back test
file passes sequentially with 3 tests.

## S28 Review

Reviewed the `W04.P07.S28` oracle payload after re-grounding the step against
the cross-period prorrata ADR, the W04/P07 plan row, the existing manual-oracle
corpus shape, and the current external-oracle enrollment gate. The change is a
single data fixture under `manual_oracles`: it records the AEAT Manual practico
IVA 2025 prorrata-general worked example from the bundled local manual, pages
137-138, with `filing_year` 2025, a raw evidence locator, the stated annual
total and con-derecho volumes, the definitive percentage, the standalone
regularización amount, and the net fourth-quarter deduction effect.

The diff does not promote `PRORRATA_REGULARIZACION`, does not edit
`_source_mesh.py`, and introduces no source kind, resolver convention,
validator convention, or registry selector shape. The current Modelo 303
registry still treats the volume fields and casilla 44 as manual at this point;
the live mesh promotion remains the planned S30 step after the S29 oracle-proof
test lands.

Findings: no open S28 implementation findings.

Residual gate inventory: the new JSON payload parses cleanly and its
`expected_by_casilla_id` keys validate as canonical casilla ids. The external
oracle enrollment test module passes when selected with the integration marker
(`2 passed`); the initial unmarked invocation was deselected by the repository's
default `-m unit` pytest configuration.

## S29 Review

Reviewed the `W04.P07.S29` oracle proof after re-grounding it against the
corrected S28 payload, the W04/P07 plan row, the cross-period prorrata ADR, the
current prorrata projection code, and the Modelo 303 registry runtime tests. The
new test is a real registry/domain path: it loads the bundled AEAT Manual
practico IVA oracle, computes the current-year definitive percentage through the
M303 2025 `4T` registry snapshot with the manual's annual volume inputs, computes
the prior-year provisional percentage from the manual's prior-year volumes, and
feeds the existing application projection with the manual's first-three-quarter
input IVA subtotal.

The test compares only against AEAT manual figures: definitive percentage `56`,
first-three-quarter deduction `934.40`, correct first-three-quarter deduction
`716.80`, excess deduction `217.60`, casilla 44 standalone regularización
`-217.60`, fourth-quarter current deduction `89.60`, fourth-quarter net effect
`-128.00`, and annual deduction `806.40`. It explicitly prevents conflating the
standalone casilla 44 amount with the manual's net fourth-quarter deduction. The
diff is test-only and does not promote `PRORRATA_REGULARIZACION`, edit
`_source_mesh.py`, or introduce a source kind, resolver convention, validator
convention, or registry selector shape.

Findings: no open S29 implementation findings.

Residual gate inventory: `ruff check` is clean for the new oracle test. The new
oracle test passes sequentially with 1 test, the adjacent prorrata regularización
calculation test file passes sequentially with 8 tests, and the external oracle
enrollment test module passes when selected with the integration marker
(`2 passed`).

## S30 Deferral Review

Reviewed the `W04.P07.S30` live source-mesh promotion after re-grounding it
against the cross-period prorrata ADR, the W04/P07 plan row, the existing
`PRORRATA_REGULARIZACION` deferred-source registry entry, and the
`iva_compensation_annual_partition` precedent. The S29 AEAT manual oracle proof
is landed, so the semantic gate for promotion is satisfied.

The implementation target is not safely editable at this point:
`src/aeat/application/aggregation/_source_mesh.py` carries non-authored
uncommitted WIP adding structured out-of-window source-diagnostic fields and
helpers. The shared-worktree safety rule requires aborting edits to a file with
non-authored WIP, so S30 is formally deferred rather than partially promoted.

Findings: no S30 implementation was attempted.

Blocker: non-authored WIP in `_source_mesh.py`.

Follow-up: rerun S30 after the `_source_mesh.py` WIP owner lands or clears that
change; enroll the `PRORRATA_REGULARIZACION` resolver in `merge_source_resolutions`
and remove it from `DEFERRED_SOURCE_KIND_TARGETS` in the same change, gated by the
S29 oracle proof.

## S31 Deferral Review

Reviewed the `W04.P07.S31` bienes-inversión unblock record against the same
source-mesh surface. The current `BIENES_INVERSION_REGULARIZACION` deferred
entry still declares `promotion_depends_on=BindingSourceKind.PRORRATA_REGULARIZACION`,
but the prerequisite S30 live promotion is formally deferred and `_source_mesh.py`
is still blocked by non-authored WIP.

Findings: no S31 implementation was attempted.

Blocker: same non-authored `_source_mesh.py` WIP as S30, plus the prerequisite
`PRORRATA_REGULARIZACION` live source remains deferred.

Follow-up: after S30 lands the live prorrata regularización source, record the
bienes-inversión casilla-43 automatic feed unblock in the source-mesh disposition
surface while preserving the existing promotion dependency.

## S32 Review

Reviewed the `W05.P08.S32` applicability projection after re-grounding it against
the cross-period prorrata ADR, the W05/P08 plan row, the prorrata register domain
model, the current declared-volume ledger rollup, and the calculate-path advisory
tests. The change adds a pure calculation-layer projection:
`derive_prorrata_applicability` returns `applies=True` when the register carries
any non-`NINGUNA` entry, when declared annual volumes imply positive sin-derecho
volume, or when the ledger rollup projects positive sin-derecho volume.

The change is deliberately diagnostic-neutral: S32 only derives applicability
evidence and does not yet emit the missing-carry calculate advisory or settlement
verify advisory owned by S33/S34. It does not touch source-kind promotion,
`_source_mesh.py`, registry bindings, resolver conventions, validator
conventions, or registry selector shape. The existing prorrata regression file
has peer WIP, so the tests landed in a new focused file instead of editing that
dirty file.

Findings: no open S32 implementation findings.

Residual gate inventory: `ruff check` is clean for the touched projection and
new test file. The new applicability test file passes sequentially with 6 tests,
and the adjacent prorrata regularización calculation test file passes
sequentially with 8 tests.

## S33 Review

Reviewed the `W05.P08.S33` missing-carry advisory after re-grounding it against
the S32 applicability projection, the prorrata register seed/service APIs, the
existing calculate-path prorrata advisory collector, the W05/P08 plan row, and
the cross-period prorrata ADR. The change adds a pure calculation-layer
diagnostic builder that returns a `PRORRATA_REGULARIZACION` source diagnostic
only when prorrata applies and the provisional percentage ladder is unresolved,
exports it through the calculation facade, and wires it into the existing
post-calculation Modelo 303 advisory fan-out.

The diagnostic names the missing operator action without fabricating a
percentage: first ejercicios must record the inicio-de-actividad percentage, and
later ejercicios must seed or record the prior definitive percentage. The live
collector loads the profile-scoped prorrata register by bucket, derives
applicability from active register entries plus available declared-volume
casillas, and emits the missing-carry diagnostic even on non-settlement periods.
It preserves the existing settlement regularización projection when a real prior
definitive percentage is available. The change does not promote source kinds,
edit `_source_mesh.py`, change registry bindings, or add
resolver/validator/selector conventions.

Findings: no open S33 implementation findings.

Residual gate inventory: `ruff check` is clean for the touched calculation
projection, calculation facade, advisory coordinator, advisory collector, and
test files. The missing-carry plus model advisory test slice passes sequentially
with 10 tests, and the adjacent applicability plus prorrata regularización
calculation slices pass sequentially with 14 tests.

## S34 Review

Reviewed the `W05.P08.S34` settlement verify advisory after re-grounding it
against the W05/P08 plan row, the cross-period prorrata ADR, the live M303
verification expectation layout, and the existing `implies_nonzero` predicate
runtime. The change adds a single fragmented M303 2023 verification predicate:
when `iva.prorrata-volumen-total` is positive and casilla `44` is zero/absent,
verification emits an ADVISORY finding rather than returning a zero-finding
`verified_complete` result.

The predicate deliberately stays within existing verification conventions. It
does not add a new predicate operator to compare annual total and con-derecho
volumes, does not promote `PRORRATA_REGULARIZACION`, and does not touch
`_source_mesh.py` or any resolver/validator convention. The non-blocking shape is
appropriate because casilla 44 can legitimately net to zero once the provisional
carry and definitive percentage are confirmed; the gate's job here is visibility,
not refusal. The focused application test loads the shipped M303 revision and
proves the warning fires for declared annual prorrata volume with zero casilla
44, stays silent when casilla 44 is non-zero, and leaves the Art. 94 no-volume
full-deduction default untouched.

Findings: no open S34 implementation findings.

Residual gate inventory: `ruff check` is clean for the touched application test.
The focused prorrata verification advisory test passes sequentially with 4 tests,
the adjacent M303 advisory slice passes sequentially with 8 tests, and
`vault check features --feature cross-period-prorrata` is clean.

## S35 Review

Reviewed the `W05.P08.S35` regression coverage after re-grounding it against the
S32 applicability projection, the S33 missing-carry diagnostic, the S34 M303
verification predicate, and the existing annual prorrata regularizacion
calculation tests. The step is correctly test-only: production behavior already
landed in S32-S34, so S35 names the non-silence contracts and proves them through
real helper and predicate evaluation tests.

The new calculation tests prove that a mixed trader with declared sin-derecho
annual volume and no provisional carry gets a missing-carry advisory instead of
a silent 100 percent in-year default; that a zero-percent definitive prorrata
still emits the casilla-44 regularizacion advisory instead of silently zeroing
the deducible side; and that a fully-taxable no-volume filing leaves the Art. 94
full-deduction default quiet. The S34 shipped-predicate test remains the
verify-time proof that a declared-volume settlement cannot silently skip casilla
44 with zero findings.

Findings: no open S35 implementation findings.

Residual gate inventory: `ruff check` is clean for the touched calculation test.
The expanded prorrata regularizacion calculation test file passes sequentially
with 11 tests, and the adjacent missing-carry plus M303 verify-advisory slice
passes sequentially with 19 tests.

## S36 Review

Reviewed the `W05.P08.S36` silent-zero-base closure reconciliation against the
live silent-zero-base plan status, the silent-zero ADR, the S03/S04 exec records,
and the July 5 silent-zero campaign-close audit. At current HEAD the
silent-zero-base plan is already complete: 18 of 18 steps, no open step, and no
missing exec records. `W01.P02.S03` and `W01.P02.S04` are checked and have
dedicated exec records explaining that per-period prorrata volume bindings would
ship wrong regulated values for mixed traders and are therefore formally
deferred to the cross-period prorrata mechanism.

No duplicate old-plan exec record was added and the existing silent-zero records
were left untouched. The S36 cross-period exec record captures the verification
that the prior plan's deferred rows are closed with the cross-period model as the
named follow-up: provisional carry, annual current-year volumes, settlement
regularizacion, and advisory-first visibility rather than fabricated per-period
bindings.

Findings: no open S36 reconciliation findings.

Residual gate inventory: `vault plan status` for
`2026-06-19-silent-zero-base-aggregation-plan` reports 18/18 complete with no
missing exec records. `vault check features` and `vault check frontmatter` are
clean for `silent-zero-base-aggregation`, and the focused prorrata regression
slice passes sequentially with 19 tests.

## S37 Review

Reviewed the `W06.P09.S37` deferred especial record against the cross-period
prorrata ADR, the W06 plan row, the register regime enum, and the IVA prorrata
domain substrate. The register carries `ProrrataRegisterRegime.ESPECIAL` from
birth and the domain substrate already exposes `is_especial_mandatory` plus the
Art. 103.Dos +10 percent comparison constant. Those are schema/substrate
capacity only: the live ledger path does not yet classify each input IVA amount
as exclusively deductible, exclusively non-deductible, or common-use for
prorrata especial apportionment.

S37 is therefore correctly recorded as a formal deferral. The follow-up is the
per-input especial classification/apportionment surface, followed by a
non-blocking Art. 103.Dos.2 mandatory-especial comparison advisory. No production
code or registry source convention changed in this step.

Findings: no open S37 reconciliation findings.

Residual gate inventory: the focused domain prorrata/register test slice passes
sequentially with 51 tests.

## S38 Review

Reviewed the `W06.P09.S38` sector follow-up record against the cross-period
prorrata ADR, the W06 plan row, the register `sector_id` slot, and the domain
sectoral prorrata predicate. The register already keys entries by
`(ejercicio, sector_id)` and rejects duplicates, and the domain substrate can
evaluate the Art. 9.1.c sectoral-separation predicate from supplied sectors.
That is schema/substrate capacity only: the application does not yet identify
taxpayer sectors, orchestrate per-sector register entries, or run per-sector
provisional/definitive lifecycle flows.

S38 correctly records three follow-ups rather than shipping implicit behavior:
per-sector register orchestration, the Art. 104.Tres financial/inmobiliario
special denominator treatment beyond the current exclusion set, and the Art.
105.Cinco interrupted-activity three-year rule. No production code or registry
convention changed in this step.

Findings: no open S38 reconciliation findings.

Residual gate inventory: the focused domain prorrata/register test slice passes
sequentially with 51 tests.

## S39 Review

Reviewed the `W06.P09.S39` ledger-rollup exclusion follow-up against the
cross-period prorrata ADR, the W06 plan row, the declared-volume divergence
helper, and the domain IVA prorrata input contract. The live rollup remains
correctly advisory-only: it windows existing IVA ledger observations with
`Period.contains`, classifies visible output volume into con-derecho and
sin-derecho buckets, and warns when the ledger projection diverges from the
operator-declared annual volume casillas.

The automatic Art. 104.Tres exclusion classification remains deferred. The
domain input contract requires the caller to supply annual totals with
subvenciones not linked to operations, autoconsumos, bienes-de-inversion
disposals, and non-recurring financial or immovable operations already excluded.
Until ledger evidence can identify those exclusions without guessing, the rollup
must stay a reconciliation check and must not become an authoritative filed
volume source.

Findings: no open S39 reconciliation findings.

Residual gate inventory: the prorrata regularizacion plus domain prorrata test
slice passes sequentially with 44 tests. `vault check features` and
`vault check frontmatter` are clean for `cross-period-prorrata`.

## S40 Campaign-Close Honesty Review

Reviewed the campaign as a fresh close reviewer against the cross-period
prorrata ADR, the L3 plan, the feature reference, the rolling exec records, the
feature commit trail, and live code search. The core general-prorrata capability
is materially implemented and guarded: register persistence/carry, provisional
IVA apportionment, settlement regularizacion projection, settlement write-back,
manual-oracle proof, missing-carry advisory, settlement verify advisory, and the
silent-zero deferral closure all have focused evidence.

### source-mesh-promotion-still-deferred | high | `PRORRATA_REGULARIZACION` is still not a live mesh source

The plan row `W04.P07.S30` is checked, but its exec record explicitly says the
source-mesh promotion was deferred because `_source_mesh.py` carried
non-authored WIP. The live code still keeps
`BindingSourceKind.PRORRATA_REGULARIZACION` in `DEFERRED_SOURCE_KIND_TARGETS`,
and the registry taxonomy test still includes it in the deferred undeclared
source-kind carve-out. That means the campaign has not fully delivered the
post-oracle source-kind promotion promised by the row text. This is not a silent
calculation defect because S33-S35/S39 keep advisory visibility and no fabricated
binding is shipped, but it is an honest open implementation item.

Tracking: added `W06.P09.S41` to promote `PRORRATA_REGULARIZACION` once
`_source_mesh.py` is owner-clean, with verification gates covering live mesh
enrollment, removal from the deferred taxonomy carve-out, source-kind parity,
the AEAT manual oracle, and the M303 prorrata advisory slice.

Residual deferrals remain intentional and already tracked by W06: prorrata
especial per-input apportionment, the Art. 103.Dos.2 +10 percent advisory,
sectores diferenciados orchestration, Art. 104.Tres financial/inmobiliario
special denominator treatment, Art. 105.Cinco, and automatic Art. 104.Tres
exclusion classification. They are schema-backed follow-ups, not hidden shipped
behavior.

S40 outcome: review complete, campaign not closed. The next open row is
`W06.P09.S41`.

Residual gate inventory: the focused close-review prorrata slice passes
sequentially with 48 tests. Feature and frontmatter vault checks are clean after
S40/S41 tracking.

## S41 Blocker Reconciliation

Reviewed the `W06.P09.S41` live source-mesh promotion against the required RAG
grounding, the S30/S40 records, the source mesh, the binding selector registry,
the application source resolver enrollment, and the Modelo 303/390 registry
surfaces.

The promotion is not safely implementable as the small source-mesh cleanup that
S40 first described. Exact source search confirms there is no
`prorrata_regularizacion` registry binding, no selector contract entry, no
binding selector registry enrollment, no prorrata live resolver, and no
application source-kind enrollment. Modelo 303 casilla 44 remains a manual input
in the current registry revisions, the current deductible-total projection does
not consume casilla 44, and no clear Modelo 390 annual regularizacion binding
target is provisioned.

A patch that only removes `PRORRATA_REGULARIZACION` from
`DEFERRED_SOURCE_KIND_TARGETS` and the deferred taxonomy carve-out would orphan
the enum and bypass the real source-provisioning path. The correct closure needs
the selector contract, registry binding or bindings, resolver, live enrollment,
formula implications, and parity/oracle/advisory tests to land together.

Tracking: `W06.P09.S41` is closed as the blocker reconciliation only. The real
promotion chain is split into W07: selector contract (`W07.P10.S42`), Modelo 303
binding provisioning (`W07.P10.S43`), Modelo 390 target grounding (`W07.P10.S44`),
resolver timing (`W07.P11.S45`), resolver materialisation (`W07.P11.S46`), live
enrollment and carve-out removal (`W07.P12.S47`), bienes-inversion dependency
reconciliation (`W07.P12.S48`), and close review (`W07.P12.S49`). No production
code changed in this reconciliation.

## S44 Review

Reviewed the `W07.P10.S44` Modelo 390 target grounding after re-running semantic
discovery, checking the current plan status, and confirming the bundled AEAT
Modelo 390 2025 record design. The official design carries page `04000` field
`[522]` at offset `642`, length `17`, type `N`, labelled as regularizacion by
application of the definitive prorrata percentage. The repaired change
provisions that target as manual
`iva.anual.regularizacion-prorrata-definitiva`, declares the future
`prorrata_regularizacion` binding row with the existing selector contract,
extends only the existing selector output literal set, adds the export-layout
field plus construct and calculation-completeness manifest coverage, and enrolls
box `[522]` in the annual deductible formula.

The initial review found no new source kind, resolver convention, or validator
convention. A later follow-up finding below superseded its safety conclusion:
the first S44 draft made box `[522]` live-bound before the resolver existed and
left the annual deductible formula without box `[522]`.

Findings: the follow-up S44 finding below was open until the repair that keeps
box `[522]` manual, retains the binding row only as future grounding, and adds
box `[522]` to the annual deductible formula.

Repair gate inventory: `ruff check` is clean for the touched Python files, the
focused M390 registry/manual-worked-example/selector pytest slice passes, and
the cross-period-prorrata frontmatter, feature-index, and plan checks are clean
after rebuilding the feature index.

### s44-m390-prorrata-target | high | bound 522 currently materialises as zero and box 64 ignores nonzero regularizacion

Follow-up review found S44 is not safe to commit as drafted. The new M390 box 522
casilla is `input_kind = "bound"` against `modelo-390-prorrata-regularizacion-anual`
while `prorrata_regularizacion` is still deferred and not observation-backed; the
registry initial-value path therefore defaults the missing casilla input to
`Decimal("0")` instead of producing an unresolved outcome. A direct calculation
probe with all other M390 carry bindings neutral and the prorrata binding omitted
materialised `iva.anual.regularizacion-prorrata-definitiva = 0` with no unresolved
outcome. The annual deductible-total formula also still sums only soportado
interiores, soportado importaciones, and autorepercutido intracomunitaria; a
nonzero 522 from the future resolver will not flow into box 64 `Suma de
deducciones` or box 65 `Resultado régimen general`. S44 must either keep the
target manual/unresolved until S45/S46 or co-land the resolver/unresolved handling
and update the M390 deductible-total formula to consume the annual prorrata
regularizacion.

Resolution: S44 was repaired as target provisioning only. Box `[522]`
`iva.anual.regularizacion-prorrata-definitiva` remains `input_kind = "manual"`
with no live casilla binding, while `modelo-390-prorrata-regularizacion-anual`
stays declared as the future `prorrata_regularizacion` selector/export grounding.
`modelo-390-iva-anual-cuota-deducible-total` now includes box `[522]`, and the
focused regression proves a nonzero operator-supplied `[522]` raises box `[64]`
and lowers box `[65]`. Automatic value materialisation remains deferred to
`W07.P11.S45` and `W07.P11.S46`.
