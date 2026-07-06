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
