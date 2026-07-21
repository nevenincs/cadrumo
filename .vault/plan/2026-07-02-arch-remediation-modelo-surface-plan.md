---
tags:
  - '#plan'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
tier: L3
related:
  - '[[2026-07-02-aeat-architecture-review-audit]]'
  - '[[2026-07-02-arch-remediation-program-adr]]'
  - '[[2026-07-02-arch-remediation-modelo-surface-adr]]'
  - '[[2026-07-06-arch-remediation-modelo-surface-research]]'
---
# `arch-remediation-modelo-surface` plan

## Wave `W01` - typed unresolved-outcome channel

Replace the M210 negative-Decimal sentinel channel with a typed unresolved-outcome member on the calculation result, deleting the sentinel constants and their rewrite shim in the same atomic change and sweeping every consumer of the result. This is the program's riskiest single edit and gates on the full M210 continuity and convenio suites; it lands before the other three moves because it changes the engine result shape they build on.

### Phase `W01.P01` - typed outcome + sentinel deletion + consumer sweep

Add the typed unresolved-outcome member to the engine result, delete the sentinels and rewrite shim, and sweep every result consumer, gated by the M210 and convenio suites.

- [x] `W01.P01.S01` - Add a typed unresolved-outcome member to the calculation engine result carrying casilla id, reason, and grounding context, riding beside the Decimal value channels rather than widening them; `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [x] `W01.P01.S02` - Emit the typed unresolved-outcome for an unresolvable M210 IRNR rate instead of a reserved negative Decimal, preserving CasillaObservation provenance through the typed outcome; `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [x] `W01.P01.S03` - Delete the M210 sentinel rate constants from the domain formula runtime in the same atomic change that lands the typed outcome, leaving no tolerance window in which both channels exist; `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [x] `W01.P01.S04` - Delete the _rewrite_m210_sentinels rewrite shim and consume the typed unresolved-outcome member to emit the BLOCKING verification finding; `src/aeat/application/modelo/_verification_actions.py`.
- [x] `W01.P01.S05` - Sweep every consumer of the calculation result to read the typed unresolved-outcome channel, confirming no site still inspects reserved negative Decimals; `src/aeat/application/modelo/_calculation_actions.py`.
- [x] `W01.P01.S06` - Confirm the M210 continuity suite and the convenio-doble-imposicion suites pass unmodified against the typed outcome; `src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py`.

## Wave `W02` - per-modelo values to declared data

Relocate per-modelo constants and exclusion sets out of the generic engine and orchestrator into registry-declared or core-declared data: the M100 imputation-days constant becomes a registry parameter (zero numeric drift), and the iva-wallet owned-binding set plus the previous-filing exclusion binding id collapse to one declaration consumed by both the validator and the mesh. Depends on W1 only for shared-file scheduling.

### Phase `W02.P02` - constants and exclusion sets to declared data

Move the M100 imputation-days constant to a registry parameter and collapse the iva-wallet ownership set plus previous-filing exclusion id to one declaration.

- [x] `W02.P02.S07` - Declare the M100 imputation-year-days value as a registry parameter on the M100 revisions in the registry authoring tree so it rides the loader and compiler; `src/aeat/_data/registry/aeat/modelos/100`.
- [x] `W02.P02.S08` - Delete the _M100_IMPUTATION_YEAR_DAYS constant from the generic formula runtime and read the value from the compiled snapshot instead; `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [x] `W02.P02.S09` - Confirm the existing grounded M100 calculation tests compute identical values before and after the parameter relocation, tolerating zero numeric drift; `src/aeat/domain/calculations/registry/tests`.
- [x] `W02.P02.S10` - Declare the iva-wallet owned relation-target binding set and the previous-filing exclusion binding id as one registry or core declaration; `src/aeat/domain/calculations/registry/_validate_relation_sources.py`.
- [x] `W02.P02.S11` - Consume the single iva-wallet ownership declaration from the registry relation-source validator, removing the inline _IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS carve-out; `src/aeat/domain/calculations/registry/_validate_relation_sources.py`.
- [x] `W02.P02.S12` - Consume the same declaration from the calculate orchestrator and delete the function-local MODELO_303_IVA_COMPENSATION_BINDING_ID import and the previous-filing exclusion shim; `src/aeat/application/modelo/_calculation_actions.py`.
- [x] `W02.P02.S13` - Confirm the M303 iva-wallet compensation continuity suite passes with ownership driven by the single declaration; `src/aeat/application/modelo/tests`.

## Wave `W03` - precedence ladder as declared data

Express the calculate-path precedence ladder (profile, mesh backend, borrador, caller, with lock-versus-carry override disposition) as ordered tier data in the aggregation package, driving the guard code from the declaration and binding a conformance test to it, the way binding ownership is already data.

### Phase `W03.P03` - precedence ladder declaration + conformance test

Declare the precedence ladder as ordered tier data and bind a conformance test to the guard order.

- [x] `W03.P03.S14` - Declare the calculate-path precedence ladder as ordered tier data carrying tier name, owned sources, and override disposition in the aggregation package; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `W03.P03.S15` - Drive the caller-override rejection ladder guard code from the declared tier data rather than sequential inline guards; `src/aeat/application/modelo/_calculation_actions.py`.
- [x] `W03.P03.S16` - Add a conformance test binding the guard order to the declared precedence tier data so the two cannot diverge; `src/aeat/application/aggregation/tests/test_precedence_ladder_conformance.py`.
- [x] `W03.P03.S17` - Confirm the lock-versus-carry override semantics are unchanged by asserting the existing override-rejection suite passes against the data-driven ladder; `src/aeat/application/modelo/tests`.

## Wave `W04` - per-modelo token ratchet gate

Land the AST ratchet gate that inventories per-modelo tokens across a named list of generic modules and ratchets the count down, making a new per-modelo branch in a generic module a CI failure unless the allowlist is consciously extended. Depends on W1 through W3 having removed the tokens the baseline records.

### Phase `W04.P04` - AST per-modelo token ratchet

Inventory per-modelo tokens across named generic modules and ratchet the count down with an allowlist.

- [x] `W04.P04.S18` - Add an AST gate that inventories per-modelo tokens matching Modelo.M-star and underscore-M-digits patterns across a named list of generic domain and application modules; `src/aeat/tests/test_generic_module_modelo_carveouts.py`.
- [x] `W04.P04.S19` - Record the post-W1-through-W3 per-modelo token count as the ratchet baseline and assert the count may only decrease; `src/aeat/tests/test_generic_module_modelo_carveouts.py`.
- [x] `W04.P04.S20` - Declare the named generic-module allowlist so a new per-modelo branch in a generic module fails the gate unless the allowlist is consciously extended; `src/aeat/tests/test_generic_module_modelo_carveouts.py`.
- [x] `W04.P04.S21` - Confirm the ratchet gate passes at the recorded baseline and fails on an injected per-modelo branch probe; `src/aeat/tests/test_generic_module_modelo_carveouts.py`.

## Description

This plan implements the per-modelo extension surface decided by the
modelo-surface ADR, discharging the audit findings that per-modelo special
cases accrete inside the generic engine and orchestrator with no declared
extension surface. It is a Wave 2/3 campaign in the remediation program: the
ADR is a Wave 2 core decision, and its four moves fan out across Wave 3.

The four moves are each independently landable and map one-to-one onto this
plan's four waves. W01 replaces the M210 negative-Decimal sentinel channel (the
sharpest instance, an implicit cross-layer contract carried by convention) with
a typed unresolved-outcome member on the engine result, deleting the sentinel
constants and the `_rewrite_m210_sentinels` shim in the same atomic change.
W02 moves per-modelo values to declared data: the M100 imputation-days constant
to a registry parameter, and the iva-wallet owned-binding set plus the
previous-filing exclusion binding id to one declaration consumed by both the
validator and the mesh. W03 expresses the calculate-path precedence ladder as
ordered tier data with a conformance test binding the guard order to the
declaration. W04 lands the AST ratchet gate that inventories per-modelo tokens
in a named generic-module list and ratchets the count down.

The ADR freezes the semantics: the aggregation-taxonomy rulings (exclusive mesh
ownership, iva-wallet ownership of the M303 compensation binding, the lock/carry
override split) survive the representation change unchanged, and
`CasillaObservation` provenance rides through the typed outcome exactly as it
rides through values today. The M100 relocation tolerates zero numeric drift.

## Steps

## Parallelization

This campaign is single-owner. The two hub files it edits repeatedly,
`_calculation_actions.py` and `_formula_runtime.py`, are contended across
concurrent campaigns in the shared worktree; the modelo-surface ADR schedules
implementation as a single-owner campaign at the Wave 2/3 boundary precisely so
fan-out workers do not add carve-outs to files this campaign is shrinking. The
four waves are therefore sequential, not parallel. W01 lands first because it
changes the engine result shape the other moves build on and is the program's
riskiest single edit. W02 and W03 are independent in principle but share the
hub files, so they run in sequence under one owner. W04 lands last because its
ratchet baseline is the per-modelo token count that only reaches its floor after
W01 through W03 have removed their tokens. Within each wave the single phase's
steps are strictly ordered (declare, then consume, then delete, then verify) per
the no-legacy atomic-change discipline.

## Verification

- W01: the M210 continuity suite and the convenio-doble-imposicion suites pass
  unmodified against the typed unresolved-outcome (W01.P01.S06), and neither the
  sentinel constants nor `_rewrite_m210_sentinels` remain in the tree
  (W01.P01.S03, W01.P01.S04).
- W02: the grounded M100 calculation tests compute identical values before and
  after the imputation-days parameter relocation, with zero numeric drift
  (W02.P02.S09), and the M303 iva-wallet compensation continuity suite passes
  with ownership driven by the single declaration (W02.P02.S13); the inline
  `_IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS` carve-out and the function-local
  `MODELO_303_IVA_COMPENSATION_BINDING_ID` import are gone (W02.P02.S11,
  W02.P02.S12).
- W03: `test_precedence_ladder_conformance.py` binds the guard order to the
  declared tier data (W03.P03.S16), and the existing override-rejection suite
  passes against the data-driven ladder (W03.P03.S17).
- W04: `test_generic_module_modelo_carveouts.py` passes at the recorded baseline
  and fails on an injected per-modelo branch probe (W04.P04.S21).
- The plan is complete when every Step is closed and each Step carries an exec
  record per the plan-closure discipline.
