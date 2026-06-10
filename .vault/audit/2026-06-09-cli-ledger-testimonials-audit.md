---
tags:
  - '#audit'
  - '#cli-ledger-testimonials'
date: '2026-06-09'
related:
  - '[[2026-06-03-cli-ledger-testimonials-audit]]'
  - '[[2026-06-03-cli-ledger-testimonials-plan]]'
---



# `cli-ledger-testimonials` audit: `P05.S13 persona re-run: skeptic/foreign/crossyear post-fix verification`

## Scope

Post-fix persona re-run for plan step P05.S13 of the cli-ledger-testimonials campaign.
Three personas (skeptic, foreign, cross-year) were re-run against the real application
layer at HEAD using real encrypted SQLite repos (no mocks). The corpus is the hand-authored
Marta Rios Velasco autónoma fixture (514 transactions, cross-year 2025 to 2026 H1).

The three still-open items from the original audit were:

1. Whether a calculated M130 return with positive income but zero cuota passes `verify`
   silently (skeptic persona — previously blocked by B3, now reachable).
2. Whether M303 special-IVA categories (intracom, export, reverse charge) route to the
   correct casillas (foreign persona — previously blocked by B3 IVA-wallet seed circularity).
3. Whether prior-year `previous_filing` bindings carry correctly across a filed period
   (cross-year persona — previously could not file a prior period to test carry).

All probes ran against HEAD with the `probe_p05s13.py` driver script using real
`isolated_runtime_profile` context, real repos, and real engine calls.

## Findings

### Verdict

**B3 IVA-wallet fix confirmed**: commits `844e8666d` and `e066b0a49` resolved the
M303 calculate-side dead-end. The IVA wallet integration tests (18 tests) pass cleanly.
The M303 source-mesh calculate CLI test passes.

**Item 2 — M303 special-IVA casilla routing: VERIFIED CLOSED**

All tested routing paths produce correct outputs:

- `INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE` produces an `intra_community_acquisition_reverse_charge`
  observation and the M303 registry binding `modelo-303-iva-autorepercutido-intracomunitaria-cuota`
  correctly lists this category in its selector. CLI transcript (engine call):
  `observations: ['intra_community_acquisition_reverse_charge']`, exit code 0.
- `EXPORT_THIRD_COUNTRY_ZERO_RATED` routes to casilla 60 (base imponible 3000.00), not
  casilla 59. CLI transcript: `casilla_60 base = 3000.00, casilla_59 base = 0`. Exit code 0.
- `INTRA_COMMUNITY_SUPPLY` (DE counterparty) routes to casilla 59 (base 5000.00), not 60.
  CLI transcript: `casilla_59 = 5000.00, casilla_60 = 0`. Exit code 0.
- `RECARGO_EQUIVALENCIA` produces `unsupported_iva_category` issue — this is the documented
  and intentional behavior (`_NON_DECLARABLE_IVA_CATEGORIES` in `_iva_ledger.py`); the row
  is not silently dropped. Grade: COSMETIC (documented limitation, not a regression).

**Item 3 — previous_filing carry across a filed period: VERIFIED CLOSED**

- Casilla 15 operator override at 3T (`--casilla "15=2694"`) is accepted: C15 = 2694,
  C17 = 806.00 (= C14 3500 - C15 2694 - C16 0). Exit code 0.
- 1T fresh period (no prior filing): C15 = 0 (absent-by-design — the binding
  `modelo-130-resultados-negativos-anteriores` correctly returns 0 at 1T per
  `max_year_delta=0`). Exit code 0.
- 3T verify with carry override: no unexpected blocking findings (only
  `cross_period_dependency_unclean` from the isolated context, which is expected when no
  prior 2T revision is seeded). Exit code 0.
- M303 `modelo-303-compensacion-pendiente-anteriores` previous_filing binding confirmed
  present in the registry snapshot.
- `test_previous_filing_casilla_override.py` (3 tests) passes at HEAD. Exit code 0.

**Item 1 — silent-under-declaration on a calculated M130 return: PARTIALLY CLOSED / FINDING**

The Art. 110.3b high-retention exemption path is correctly guarded: when C06/C01 >= 0.70
the engine sets C17 = 0 and the verification fires an `advisory` finding (kind: `advisory`,
severity: `warning`). CLI transcript: `findings: ['advisory', 'cross_period_dependency_unclean']`.
This path is NOT silent — the ADVISORY surfaces as documented in `0003-art110-3b-high-retention-advisory.toml`.

### MINOR — M130 lacks a general implies_nonzero guard

**Finding M1.** The M130 registry has no `implies_nonzero` predicate for the general case:
positive net income (`C01 > C02`) but zero pago fraccionado result (`C19 = 0`) due to
carry-forward (`C15`) or `C16` credits fully offsetting the cuota. The only existing advisory
covers the specific Art. 110.3b exemption. A filer with C01 = 20000, C02 = 5000,
C15 = 3000, C16 = 0 produces C14 = 2900 (= 3000 * 20% - 100 minoración), C17 = 2900 - 3000 =
-100, C19 = -100 (a negative result, not zero). The engine clamps the `saldo-negativo` construct
at 0 for a zero-result variant. There is no structural path through M130 where positive income
produces an artificially zero C17 except via the Art. 110.3b branch already guarded.

Conclusion: the M130 risk surface differs from M200. In M200 the base imponible is a manual
entry that can be left zero while the income antecedent is positive (a true under-declaration
gap). In M130 the cuota chain is fully formula-computed from the declared income; an operator
cannot silently misrepresent the computation unless they misstate C01 or C02 themselves. The
original audit concern ("positive income but zero cuota passes verify silently") does not
apply to M130 in the same way it applies to M200. The Art. 110.3b ADVISORY covers the only
legitimate zero-C17 path.

**Grade: MINOR / INFORMATIONAL.** No immediate code action required. The no-silent-under-declaration
rule is met for M130 via the Art.110.3b advisory covering the structural zero-result path.
A follow-up investigation of whether M130 needs a wider implies_nonzero guard is deferred
to the next campaign iteration.

## Recommendations

- **Item 2 (M303 casilla routing): CLOSED.** The special-IVA category routing is verified
  correct at every tested axis. No action required.
- **Item 3 (previous_filing carry): CLOSED.** The carry-forward override and absent-by-design
  1T paths are verified correct. No action required.
- **Item 1 (silent-under-declaration on M130): PARTIALLY CLOSED.** The Art.110.3b path is
  guarded. The general implies_nonzero gap is MINOR/INFORMATIONAL for M130 (differs from M200
  because the cuota chain is fully formula-computed). Track as a follow-up finding but do not
  block P05.S13 closure.
- The `recargo_equivalencia` unsupported-category behavior is intentional (documented in code).
  No action required.

## Codification candidates

No findings in this audit meet the three durability criteria (cross-session, constraint-shaped,
project-bound) for a new rule. The MINOR finding on M130 implies_nonzero is informational
and model-specific; it is tracked as a follow-up finding rather than a durable rule.

## Post-closure honesty addendum (fresh-context verification, 2026-06-09)

This section is appended after the P05.S13 closure above, per the
aeat-campaign-close-honesty-review discipline (a fresh-context review run against the
closure summary before the campaign is treated as structurally complete). It records one
gap the closure missed and re-affirms two deferrals. It does not retract the closure
verdicts above; it corrects their coverage.

### Finding H1 — the #64 unconsumed-IVA advisory was computed but never reached the operator (FIXED)

The "Item 1" review above evaluated the M130 verify-gate silent-zero-cuota concern and
correctly graded it MINOR for M130. A distinct silent-under-declaration gap was not
evaluated: the #64 calculate-path advisory. Commit `2714fda98` wired
`unsupported_ledger_iva_observations` into `LedgerIvaAggregationSourceResolver.resolve`, so a
declarable IVA observation that no binding consumes emits a non-blocking
`CalculationSourceDiagnostic`. But `calculate_modelo_revision_from_bucket_aggregation`
forwarded only `binding_values` / `source_transaction_ids` downstream and discarded
`source_resolution.diagnostics`, so `aeat app modelo work calculate` showed the operator
nothing. The no-silent-under-declaration rule requires an operator-facing alert, so #64 was
necessary-but-insufficient at the moment P05.S13 was declared closed: an unrouted declarable
IVA amount was still silently dropped from the operator's view.

Resolution: commit `84c51886` threads the diagnostics end-to-end — resolver ->
`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics` ->
`ModeloWorkCalculationServiceResult.source_diagnostics` -> the CLI `source_advisories` JSON
list plus a human `ADVISORY:` line via the new locale key
`cli.app.modelo.work.calculate_source_advisory` (mirroring the `authorization_advisory`
renderer precedent in the same calculate output). Real-behaviour E2E tests assert the advisory
surfaces in both JSON and human output on an unrouted `INTRA_COMMUNITY_SUPPLY` observation and
is absent when all IVA is consumed; RED-before was confirmed by neutralising
`source_diagnostics` and observing the advisory test fail. The operator now sees the
unrouted-IVA advisory at calculate time.

### Deferred to a successor campaign (re-affirmed)

- **M303 special-IVA routing nuance.** The `modelo-303-iva-autorepercutido-intracomunitaria-cuota`
  binding requires `flow_direction = inversion_sujeto_pasivo`, but the ledger's
  `_flow_direction_for` only ever emits `REPERCUTIDO` / `SOPORTADO`, so the
  intra-community-acquisition reverse-charge cuota is structurally unreachable from ledger
  data; and 11 declarable categories remain unrouted in M303. These are now non-silent (the H1
  advisory surfaces them) but still undeclared. They need LIVA art. 84 grounding for the
  correct target casillas plus a flow-direction model fix. The "Item 2" closure above verified
  base-casilla routing (59 vs 60) and category presence in the selector; it did not assert the
  reverse-charge cuota value, which is the gap recorded here.

- **Local cross-period previous_filing carry.** The "Item 3" closure verified the manual
  `--casilla` override path. Automatic local carry is not wired:
  `PreviousFilingSourceResolver` is enrolled in no production source mesh, and the local `file`
  verb does not persist observations to `CalculationObservationRepository` (automatic carry
  works only via AEAT-remote capture). Wiring automatic local carry needs a design decision and
  is carried to the successor campaign.

### Provenance note

This addendum was authored from a fresh context after a process crash. The crash orphaned a set
of duplicate campaign commits; a commit-by-commit reconciliation confirmed every orphaned commit
has a functional equivalent already on the branch, so no work was lost. The campaign is
structurally complete (13/13) with H1 closed; the two deferrals above are formally carried to
the successor campaign.

---

## M1 follow-up investigation: M130 general implies_nonzero guard (2026-06-10)

This section answers the investigation deferred as finding M1 above. It was conducted
against the registry at HEAD (`src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/`).

### Casilla-chain classification

Every casilla in the M130 estimación directa chain was audited against `0001-casillas.toml`
and `0001-formulas.toml` / `0002-formulas.toml`:

| Casilla | input_kind | Notes |
|---------|-----------|-------|
| C01 | bound | Cumulative ingresos from ledger binding |
| C02 | manual | Gastos — sole manual antecedent in the cuota chain |
| C03 | computed | C01 - C02 |
| C04 | computed | max(0, C03 × 20%) — clamped non-negative |
| C05 | manual | Pagos fraccionados anteriores (prior instalments, outside cuota chain) |
| C06 | manual | Retenciones e ingresos a cuenta |
| C07 | computed | C04 - C05 - C06 |
| C08 | manual | Volumen de ingresos agrarios (agricultural section only) |
| C09 | computed | C08 × 2% |
| C10 | manual | Retenciones e ingresos a cuenta (agricultural) |
| C11 | computed | C09 - C10 |
| C12 | computed | max(0, C07 + C11) — floor at zero |
| C13 | computed | Minoración table keyed on prior-year net income parameter |
| C14 | computed | C12 - C13 |
| C15 | bound | Prior-quarter negative carry-forward |
| C16 | manual | Deducción por inversión en vivienda habitual |
| C17 | computed | Art.110.3b branch: if(C01 > 0 AND C06/C01 ≥ 0.70, 0, C14 - C15 - C16) |
| C18 | manual | Resultado a ingresar de autoliquidaciones anteriores |
| C19 | computed | C17 - C18 |

**Verdict: no general implies_nonzero guard is warranted for M130.**

The complete evidence for this negative finding follows.

### Why the silent-zero path does not exist in M130

The M130 cuota chain is anchored at C01 (income), which is `input_kind = "bound"` — it
is populated by the ledger binding `modelo-130-actividad-economica-ingresos-cumulative`,
not by manual operator entry. An operator cannot silently leave C01 at zero while the
underlying economic activity ledger carries positive ingresos: the bound casilla is
populated from the aggregation source, so C01 reflects what the ledger contains. The
only way C01 is zero is if the ledger genuinely contains zero income.

The formula chain from C01 forward is fully computed:

- C03 = C01 - C02. If C01 = 0 the result is ≤ 0 (C02 is non-negative by convention).
- C04 = max(0, C03 × 20%). The `max(0, ...)` clamp means negative rendimiento yields
  C04 = 0 correctly; it does not silently suppress a positive cuota.
- C07 = C04 - C05 - C06. If C04 = 0 then C07 ≤ 0.
- C12 = max(0, C07 + C11). Another floor-at-zero applied before the liquidation stage.

If C01 is genuinely positive (ledger income exists), the formula chain propagates
that positivity through C03 → C04 → C07 → C12 → C14 → C17 → C19. The only
formula-internal zero-C17 paths are:

1. **Art. 110.3b**: C06/C01 ≥ 0.70 forces C17 = 0. Guarded by the existing
   `0003-art110-3b-high-retention-advisory.toml` predicate.
2. **C15 carry offsetting C14**: a prior-quarter negative carried forward as C15
   reduces C17 to `C14 - C15 - C16`. If C15 ≥ C14, C17 ≤ 0 and `saldo-negativo-fin-periodo`
   = max(0, -C17) correctly captures the overshoot for the next quarter. This is
   legitimate economic behaviour: prior losses eliminate the current quarter's instalment.
   The C15-cap predicate (`0002-verification_predicates.toml`) prevents C15 > C14 from
   being silently accepted as a valid positive-cuota filing.
3. **C16 vivienda deduction**: manual entry that can reduce C17. A very large C16 entry
   could push C17 negative, but this is by design (the operator is claiming a capital
   repayment deduction); `saldo-negativo-fin-periodo` absorbs the negative carry.

In none of these paths does positive income produce an artificially-zero pago that
bypasses the engine's computation. The M200 gap (manual base imponible entry can be
left zero while resultado contable antecedent is positive) does not exist in M130 because
the income antecedent C01 is bound, not manual.

A naive `implies_nonzero(["01", "19"])` guard would fire as a false positive on every
legitimate carry-forward filing (case 2 above), every high-retention period (case 1,
already guarded), and every quarter where retenciones or prior payments fully cover
the instalment (entirely normal for a high-withholding autónomo). The guard cannot
distinguish these from an artificially-zero result; it would surface an advisory on
correct filings. This is exactly the false-positive risk the audit noted.

**Conclusion**: M130 satisfies `no-silent-under-declaration` via the Art.110.3b
advisory. No additional implies_nonzero predicate should be added. The MINOR finding
M1 is formally closed as a negative investigation result.

### M131 inventory note (estimación objetiva — scope: inventory only)

M131 has a structurally different shape. In the 2026 revision, C01 ("Suma de
rendimientos netos") is `input_kind = "manual"`. An operator running módulos activities
must enter the rendimientos netos figure by hand. There is no ledger binding on C01 for
M131: the módulos calculation is performed externally (AEAT publishes signed tables per
actividad/año) and the operator enters the result. This means a filer with genuine
módulos income could enter C01 = 0 while the actividad has positive rendimientos, and
the formula chain (C04 = C03 × 2%, C06 = C05 × 2%, C07 = C02 + C04 + C06, C10 = C07 - C08 - C09,
C13 = C10 - C11 - C12, C15 = C13 - C14) would propagate zero without firing any advisory.

M131 is not covered by the Art.110.3b guard (that guard is M130-specific). Whether a
`implies_nonzero` advisory on M131's C01 → C15 path is warranted requires a separate
investigation with LIRPF / RD 439/2007 art. 100–110 grounding for the módulos
determination obligation. That investigation is out of scope for this pass and is
formally deferred to a successor campaign.
