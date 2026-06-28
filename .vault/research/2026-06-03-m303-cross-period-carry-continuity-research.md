---
tags:
  - '#research'
  - '#m303-cross-period-carry-continuity'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-06-03-m303-synthetic-generator-primitive-spec-adr]]'
  - '[[2026-06-03-synthetic-fixture-primitive-encoding-discipline-adr]]'
  - '[[2026-06-02-m303-parser-engine-totals-impedance-adr]]'
  - '[[2026-06-01-m303-form-vs-semantic-casilla-dual-keying-adr]]'
---

# `m303-cross-period-carry-continuity` research: M303 cross-period compensación carry continuity regression after primitive-encoding

## Why this research

Three tests in `src/aeat/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py`
are red on HEAD after `6e5a316a6 fix(m303): wire primitive cuota leaves into
synthetic fixtures and extractor` landed: `test_year_n_4t_credit_produces_carry_forward_saldo`,
`test_year_n_plus_1_1t_casilla_110_auto_resolves_from_prior_year_4t`, and
`test_modelo_303_compensacion_carry_enrolls_two_renta_years`. All three fail
on `assert carried_saldo > Decimal("0")` (or its sibling, the wiring assert
`resolved.get(_CARRY_RELATION) == carried_saldo`). The 47/47 reds the
primitive-encoding commit closed were per-period engine-recomputation
correctness (`test_verification_chain.py`); they did not exercise the
**cross-period** carry chain that wraps a prior 4T into the next 1T's
casilla 110 — the contract this module ratchets. The diagnostic shape is
therefore: a regression introduced by the per-rate primitive encoding,
hidden by the verification-chain's in-period scope, surfaced only by the
cross-period continuity gate. The work below traces every casilla and
binding on that carry chain at HEAD to identify which link snapped.

## Carry chain at HEAD (2023-y-siguientes revision)

The full chain from the year-N 4T credit scenario to year N+1 1T's
casilla 110 resolution:

1. **Credit-side input.** The test calls `_calculate_303` with
   `cuota_binding_overrides = {modelo-303-iva-repercutido-general-cuota: 21,
   modelo-303-iva-soportado-interiores-cuota: 63}`. These binding values
   resolve through `resolve_bound_casilla_inputs` into casilla inputs on
   `iva.repercutido.general` and `iva.soportado.interiores` (the primitive
   leaves the engine recomputes the per-section totals from).

2. **Engine: per-section totals.** `iva.cuota-devengada-total` =
   `iva.repercutido.general + reducido + super-reducido +
   autorepercutido.intracomunitaria + iva.autoconsumo.promotor.cuota`.
   `iva.cuota-deducible-total` = `iva.soportado.interiores +
   iva.autorepercutido.intracomunitaria`. With the test inputs:
   devengada = 21 + 0 + 0 + 0 + (0 * 0.21) = 21; deducible = 63 + 0 = 63.

3. **Engine: régimen general result.** `iva.resultado-regimen-general` =
   `iva.cuota-devengada-total - iva.cuota-deducible-total` = 21 - 63 = -42.
   This is the credit that becomes the saldo a compensar (LIVA art. 99).

4. **Engine: aggregate row.** `64` = `iva.resultado-regimen-general + 58 +
   76` = -42 + 0 + 0 = -42. `66` = `64 × 65 / 100` = -42 × 100 / 100 = -42
   (state-attribution-ratio binding = 100 for territorio común).

5. **Engine: prior-period applied.** `iva.compensacion-aplicada-periodo` =
   `min(iva.compensacion-pendiente-periodos-anteriores, max(0,
   iva.resultado-regimen-general))` = `min(0, max(0, -42))` = `min(0, 0)`
   = 0 (for year-N 4T there is no prior carry-in; default binding = 0).

6. **Engine: `iva.resultado`.** `iva.resultado` =
   `(66 + 77 + 68) - iva.compensacion-aplicada-periodo` = (-42 + 0 + 0) - 0
   = -42. The "auto-liquidación" row remains negative.

7. **Engine: generated saldo.** `iva.compensacion-generada-periodo` =
   `max(0, negate(iva.resultado))` = `max(0, 42)` = 42. The credit becomes
   a saldo a compensar generated this period.

8. **Engine: posteriores carry-out.** `iva.compensacion-pendiente-periodos-posteriores`
   = `iva.compensacion-pendiente-periodos-anteriores - iva.compensacion-aplicada-periodo`
   = 0 - 0 = 0. (For a period with no prior carry-in and no positive
   result, no prior balance is rolled.)

9. **Engine: end-of-period balance.** `iva.compensacion-disponible-fin-periodo`
   = `iva.compensacion-pendiente-periodos-posteriores + iva.compensacion-generada-periodo`
   = 0 + 42 = 42. **This is the value `_SALDO_CASILLA` the test reads
   from `result.values`.**

10. **Persistence.** The test wraps `result.values` into a
    `RegistryModeloObservation` via `_registry_observation`, which builds a
    `tuple(CasillaObservation(casilla_id=cid, value=val) for cid, val in
    result.values.items())`. The `obs_repo.save_observation` call lands it
    in the encrypted-SQLite store under
    `(modelo='303', filing_year=2025, period='4T')`.

11. **Cross-renta wrap.** For year N+1 1T, the test calls
    `resolve_relations_from_local_store(snapshot_n1, repository=obs_repo)`.
    This walks the snapshot's relation requirements; for the carry
    relation it identifies the source period (1T offset by -1 = prior 4T,
    revision-selector `filing_year_delta = 0` plus `period_alignment.mode
    = "previous_quarter"` wraps the year back by one — verified in
    `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml`
    lines 558-577), and resolves the value via
    `_resolve_requirement_value` → `_observed_requirement_values`. The
    requirement's `source_output` is `iva.compensacion-disponible-fin-periodo`;
    the resolver reads
    `observation.casilla_values.get("iva.compensacion-disponible-fin-periodo")`
    (verified in `src/aeat/application/calculations/_relation_prefill.py`
    line 240). Match → returns the value.

12. **Year N+1 1T computation.** `materialize_relation_binding_values`
    copies the resolved relation value into the binding
    `modelo-303-compensacion-pendiente-anteriores`, which is the binding
    for casilla 110 (`iva.compensacion-pendiente-periodos-anteriores`).
    The engine then computes the period with the inherited carry-in
    available.

## Verification points against HEAD

The following were verified by reading the registry, the relation
resolver, and the test module on the current HEAD (`f6ae3c35e` plus the
local `.vault/exec/` edit on `2026-05-27-schema-hardening-placeholder-eradication.md`):

- `iva.compensacion-pendiente-periodos-anteriores` (casilla 110) is the
  binding-side casilla whose binding `modelo-303-compensacion-pendiente-anteriores`
  is the `target_binding` of the carry relation. Verified at
  `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`
  lines 200, 209.
- `iva.compensacion-disponible-fin-periodo` is the relation's
  `source_output`. Verified at the same `revision.toml` line 563.
- The relation resolver pulls a TOTAL casilla, not a primitive. The
  `source_output` is `iva.compensacion-disponible-fin-periodo`, a
  **computed** casilla whose formula is the saldo derivation above
  (`revision.toml` lines 515-534, `iva.compensacion-pendiente-periodos-posteriores
  + iva.compensacion-generada-periodo`).
- `iva.compensacion-disponible-fin-periodo` IS in
  `computed_casillas` and therefore IS included in `result.values` for
  any successful engine run (`revision.toml` line 25).
- The 2009-y-siguientes (legacy) revision has the same chain shape with
  no `iva.autoconsumo.promotor.*` participation in the devengada total —
  the legacy `iva.cuota-devengada-total` formula sums four leaves
  (general + reducido + super-reducido + intracomunitaria), not five
  (`revision.toml` lines 557, plus the parallel formula). The carry
  shape is otherwise identical (relation id, source_output, target,
  selector). The test year N (2025) and N+1 (2026) both use the
  2023-y-siguientes revision; the legacy revision is not on the test
  path.

## Candidate diagnoses

Three plausible failure modes survive the chain trace. Each is testable
in the diagnostic Phase of the plan.

### Hypothesis A — `iva.resultado` chain emits zero on credit scenario

The most likely cause given the regression timing. The primitive-encoding
commit added `iva.autoconsumo.promotor.cuota` (the **computed** leaf
multiplying `iva.autoconsumo.promotor.base * 0.21`) as an explicit
addend in the new `iva.cuota-devengada-total` formula
(`revision.toml` lines 201-206). The base binding
`modelo-303-autoconsumo-promotor-base` is `source = "profile"`
(`revision.toml` lines 146-160) and is supplied by the test as a
WORKAROUND constant 0 — verified safe.

The deeper risk: the engine's evaluation order may now compute
`iva.cuota-devengada-total` BEFORE the engine knows that the autoconsumo
cuota leaf is computed-not-bound. If the engine attempted to resolve
`iva.autoconsumo.promotor.cuota` from the input mapping (which is empty
for that key), the engine refuses or defaults to zero with no error,
and the entire downstream chain could collapse. The diagnostic Step
must `print(result.values)` for the year-N 4T run and verify each
casilla in the chain (devengada-total / deducible-total /
resultado-regimen-general / 64 / 66 / resultado / generada-periodo /
disponible-fin-periodo).

### Hypothesis B — `result.values` keys changed shape; observation lookup misses

The primitive-encoding commit may have changed which casilla IDs land
in `result.values` (added primitive IDs alongside or in place of total
IDs). The `_observed_requirement_values` lookup at
`_relation_prefill.py` line 240 reads
`matches[0].casilla_values.get(requirement.source_output)` where
`source_output = "iva.compensacion-disponible-fin-periodo"`. If
`result.values` no longer contains that key (renamed, split, or absent
for credit scenarios), `value is None` → `RegistryValidationError`,
but the test does NOT assert on the exception shape; it asserts on
`carried_saldo > 0`. If the assertion fires earlier (the year-N 4T
`_SALDO_CASILLA` lookup raises `KeyError` on `result.values[_SALDO_CASILLA]`),
the test would FAIL with KeyError, not the documented `assert carried_saldo
> 0`. Distinguishing A from B requires reading the actual pytest output —
the failure-mode trace is the discriminator.

### Hypothesis C — relation resolver short-circuits when source value <= 0

The relation source_output is a TOTAL (`compensacion-disponible-fin-periodo`).
If the engine produces it as `Decimal("0.00")` for the credit scenario
(e.g. because `iva.resultado` came out non-negative for some reason),
the observation carries 0; the resolver copies 0 into casilla 110; the
test correctly observes 0 == 0 wiring but `carried_saldo > 0` fails.
This collapses to Hypothesis A's chain-trace: the only way the saldo
becomes 0 in a credit scenario is if `iva.resultado >= 0`, which in
turn requires `iva.resultado-regimen-general >= 0`, which in turn
requires `iva.cuota-devengada-total >= iva.cuota-deducible-total`. The
primitive-encoding commit changed how each of those is computed; the
chain trace pins which step diverges from the spec.

## Cross-cluster: M390 annual consolidation

The autoconsumo-promotor surface is shared with M390 (annual M303
consolidation), per `2026-06-02-m390-annual-autoconsumo-promotor-source-adr`.
M390 reads the same `iva.compensacion-disponible-fin-periodo` saldo
out of the four quarterly M303 observations and consolidates them.
This research's scope is the M303 cross-quarter relation only; if the
diagnostic surfaces that the regression is in the autoconsumo formula
(`modelo-303-autoconsumo-promotor-cuota = iva.autoconsumo.promotor.base
* 0.21`), the M390 consolidation will inherit the same regression and
a sibling ADR will be needed to track the M390 surface. For task #167
in scope: M303 only.

## Single-rate filer invariant (per v2 spec)

The v2 ADR (`2026-06-03-m303-synthetic-generator-primitive-spec-adr`)
Findings section pins the corrected primitive encoding as 6 cuota-only
leaves (5 for legacy): `iva.repercutido.general / reducido /
super-reducido`, `iva.autorepercutido.intracomunitaria`,
`iva.autoconsumo.promotor.base` (2023+ only),
`iva.soportado.interiores`. The single-rate filer pattern places all
devengada on `iva.repercutido.general` and all deducible on
`iva.soportado.interiores`; sums of the other leaves are zero. Per
Finding 4 of that ADR, this preserves devengada-total = c27 and
deducible-total = c29 for the synthetic corpus — i.e. it preserves
per-period totals.

What the v2 spec does NOT pin is **per-period c69 (`iva.resultado`)**.
If the new chain inserts a step that consumes `iva.compensacion-aplicada-periodo`
in a way that previously zeroed silently and now zeroes loudly (or
vice versa), c69 can change while c27 and c45 are preserved. The
present test is the canary for that divergence.

## What the diagnostic Step must produce

A short script (or temporary test instrumentation) that runs the
year-N 4T branch of `_calculate_303` and prints each casilla in the
chain:

```text
iva.repercutido.general            = ?
iva.cuota-devengada-total          = ?
iva.soportado.interiores           = ?
iva.cuota-deducible-total          = ?
iva.resultado-regimen-general      = ?
64                                 = ?
65                                 = ?
66                                 = ?
77                                 = ?
68                                 = ?
iva.compensacion-pendiente-periodos-anteriores = ?
iva.compensacion-aplicada-periodo  = ?
iva.resultado                      = ?
iva.compensacion-generada-periodo  = ?
iva.compensacion-pendiente-periodos-posteriores = ?
iva.compensacion-disponible-fin-periodo = ?
```

The first row that diverges from the chain narrative in §"Carry chain
at HEAD" pins the broken link. The ADR phase commits to a fix shape
based on which row diverged.

## Source artefacts read

- `src/aeat/application/calculations/test_modelo_303_compensacion_carry_forward_continuity.py`
- `src/aeat/application/calculations/_relation_prefill.py`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/revision.toml`
- `.vault/adr/2026-06-03-m303-synthetic-generator-primitive-spec-adr.md`
- `.vault/adr/2026-06-03-synthetic-fixture-primitive-encoding-discipline-adr.md`
- `.vault/adr/2026-06-02-m303-parser-engine-totals-impedance-adr.md`
- `.vault/adr/2026-06-01-m303-form-vs-semantic-casilla-dual-keying-adr.md`
- Commit `6e5a316a6 fix(m303): wire primitive cuota leaves into synthetic fixtures and extractor`
