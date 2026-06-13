---
tags:
  - '#research'
  - '#renta-cuota-integra-state-scale'
date: '2026-05-08'
modified: '2026-05-08'
related: []
---

# `renta-cuota-integra-state-scale` research

Grounding for wiring the IRPF state-level progressive bracket tables
(`renta-{2020..2025}-escala-estatal-base-general`) into Modelo 100's
formula chain so that `cuota íntegra estatal` is computed end-to-end
instead of relying on operator-typed inputs at casillas 0528 and 0530.

## Mandate and scope

Spanish IRPF computation is legally mandated end-to-end. The state
portion of the cuota íntegra (LIRPF arts. 62-63 and arts. 67) is
derived from the base liquidable general by applying the state
progressive scale. The same scale is applied to the personal/family
minimum so the operator's net cuota subtracts the minimum's tax cost.
Both inputs to the eventual `0532 = 0528 - 0530` subtraction are
bracket-lookup outputs of the same scale parameter.

The registry already carries:

- the bracket-table parameter `renta-{year}-escala-estatal-base-general`
  with full marginal-rate schedules per ejercicio (2020-2025), legal
  refs `ley-35-2006:art-62` and `ley-35-2006:art-63`, source citation
  `lirpf-cuota-chain-authority`;
- the formula runtime op `lookup_bracket` (`aeat.domain.calculations.
  registry._formula_runtime.py:164`), which accepts a base value and
  a bracket-table parameter reference and returns the cuota via
  `_resolve_bracket`;
- the casillas 0528, 0529, 0530, 0531, 0532, 0533, 0540, 0541, 0545,
  0546 with section taxonomy `["resultados", "calculo_impuesto_res",
  "gravamenes_res"]` and full per-year legal refs.

What is missing: the formula declarations that bind the bracket-table
parameter into the formula evaluator at the four casilla targets that
need it.

## Casilla map (per ejercicio)

The state-side chain (state portion of the cuota):

| casilla | role                                                                | currently      |
| ------- | ------------------------------------------------------------------- | -------------- |
| 0505    | base liquidable general                                             | computed       |
| 0521    | mínimo personal y familiar (state portion)                          | computed       |
| 0528    | apply state scale to 0505 -> state portion                          | manual input   |
| 0530    | apply state scale to 0521 -> state portion                          | manual input   |
| 0532    | `0528 - 0530` (cuota base liquidable general estatal)               | computed       |
| 0540    | additional state cuota (special-rate income, capital gains, etc.)   | manual / other |
| 0545    | `0532 + 0540` (total state cuota integra)                           | computed       |

Same shape on the autonomic side (0506 / 0523 / 0529 / 0531 / 0533 /
0541 / 0546). Autonomic is **not in scope of this research** - the
autonomic scale is CCAA-specific (17 comunidades + 2 ciudades
autonomas), each publishing its own per-year scale. That is a
separate, larger research stream tracked under a follow-up.

## Reference: existing formula precedent

`renta-2020-cuota-base-liquidable-general-estatal` (target 0532)
already declares the subtract closure that consumes 0528 and 0530:

```toml
[[revisions."2020".formulas]]
id = "renta-2020-cuota-base-liquidable-general-estatal"
target = "0532"
expression = { op = "subtract", args = [
    { casilla = "0528" },
    { casilla = "0530" },
] }
```

Its inputs (0528, 0530) are currently manual-entry casillas. Wiring a
`lookup_bracket` formula at each input target promotes the chain to
fully computed and removes the operator-typed cuota interjection.

## Reference: lookup_bracket op contract

`aeat.domain.calculations.registry._formula_runtime._evaluate_expression`
implements `op = "lookup_bracket"` with the contract:

- `args[0]` - any expression yielding the base value (the casilla
  whose value is the input to the bracket schedule, e.g. 0505 or
  0521);
- `args[1]` - a parameter leaf whose `data_type` is `bracket_table`;
- the runtime calls `_resolve_bracket(bracket_param, base,
  date_context)` and emits the cuota.

Form for the missing 0528 formula (worked example for revision 2020):

```toml
[[revisions."2020".formulas]]
id = "renta-2020-cuota-escala-estatal-sobre-base-liquidable-general"
target = "0528"
expression = { op = "lookup_bracket", args = [
    { casilla = "0505" },
    { parameter = "renta-2020-escala-estatal-base-general" },
] }
rounding = "money-2"
legal_refs = ["ley-35-2006:art-62", "ley-35-2006:art-63"]
source_refs = ["lirpf-cuota-chain-authority"]

[[revisions."2020".formulas.source_citations]]
source_ref = "lirpf-cuota-chain-authority"
required_text = ["escala general", "base liquidable general"]
```

Mirror declaration for 0530 (target = "0530", `casilla = "0521"`).

## AEAT live-oracle grounding

The Renta WEB Open driver (`aeat.adapters.outbound.aeat.sede` test
harness) captured the live AEAT calculator's responses for a baseline
employee profile across the supported ejercicios. The captured
payloads include the cuota integra state portion and serve as the
parity oracle for the lookup_bracket implementation: per-revision,
the registry's computed 0528 and 0530 must match AEAT's value to the
cent. Workbook parity refs already exist on each Modelo 100 revision
and pin the workbook source for cross-checking.

This means the wiring work is **not guesswork** - every formula
landed has an external authority (AEAT live oracle, workbook parity,
LIRPF arts. 62-63 source citations) it must agree with.

## Closure: validation pipeline coverage

Once the formulas land, the test gates that already exist in
`src/aeat/domain/calculations/registry/test_modelo_100_drift_detection.py`
will confirm closure automatically:

- `test_no_orphan_parameters_in_any_revision` - the new formulas
  reference the bracket parameters via `{ parameter = "..." }`, so
  the orphan-detection gate clears the six `escala-estatal-base-general`
  entries that currently sit in the `_PRE_STAGED_PARAMETERS`
  allow-list. The allow-list shrinks accordingly.
- `test_every_formula_parameter_reference_resolves_to_a_declared_parameter`
  - confirms each `parameter = "renta-{year}-escala-estatal-base-general"`
  reference points at a declared parameter (already passes; will
  continue to pass).
- workbook parity tests - exercise `_resolve_bracket` against AEAT's
  workbook and assert per-bracket arithmetic.

## Out of scope

- **Autonomic scale (`escala-autonomica-base-general` per CCAA)** -
  17+2 jurisdictions x 6 years; data does not exist in the registry
  yet. Tracked as a follow-up research stream.
- **Special-rate income (`0540` / `0541`)** - the cuota integra
  contains an additional component for capital gains and other
  special-rate income (LIRPF arts. 66 / 76). Not part of the
  state-scale wiring; tracked separately.
- **Intra-comunitarian transfer pricing** - orthogonal.
