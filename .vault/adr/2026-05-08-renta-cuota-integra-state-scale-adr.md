---
tags:
  - '#adr'
  - '#renta-cuota-integra-state-scale'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-renta-cuota-integra-state-scale-research]]"
---

# `renta-cuota-integra-state-scale` adr | (**status:** `accepted`)

## Problem Statement

The IRPF state-level progressive bracket tables
(`renta-{2020..2025}-escala-estatal-base-general`) sit in the registry
with full marginal-rate data and a `lirpf-cuota-chain-authority`
source citation, but no formula consumes them. The casillas that
should be computed by applying that scale to the base liquidable
general (0528) and to the personal/family minimum (0530) are
currently manual-input — operators must type the cuota themselves.
Six parameters across six ejercicios (2020-2025) sit in an
allow-list (`_PRE_STAGED_PARAMETERS` in
`src/aeat/domain/calculations/registry/test_modelo_100_drift_detection.py`)
explicitly because their consuming formula chain has not landed.

## Considerations

- LIRPF arts. 62-63 mandate that the state cuota integra be computed
  from the state progressive scale applied to the base liquidable
  general; the calculation outcome is legally fixed.
- The registry's formula runtime already supports `op =
  "lookup_bracket"` (`src/aeat/domain/calculations/registry/
  _formula_runtime.py:164`) with the contract `[base_value,
  parameter_ref]` returning the cuota; no runtime extension is
  required.
- AEAT's live Renta WEB Open simulator and the published workbook
  parity refs are external authorities — every formula landed must
  agree with both to the cent (per the project's no-tautological-tests
  rule).
- The autonomic scale (CCAA-specific) is a separate, much larger
  scope — 17+2 jurisdictions per year — and is explicitly excluded.
- Six ejercicios (2020, 2021, 2022, 2023, 2024, 2025) must be wired
  symmetrically; each year's formulas must reference that year's
  bracket parameter.

## Constraints

- Concurrent agents are actively committing to
  `registry/aeat/modelos/100.toml`. Edits must be small, focused, and
  pushed quickly to minimise merge-collision risk.
- Pre-commit hooks (ruff, ty, prek) gate every commit; commits that
  unrelated registry data make fail must not block this work.
- The `_PRE_STAGED_PARAMETERS` allow-list shrinks as formulas land;
  the orphan-detection gate must continue to pass at every step.

## Implementation

Two formula declarations per ejercicio, both using `op =
"lookup_bracket"`:

```toml
# casilla 0528: state cuota for the base liquidable general
[[revisions."{YEAR}".formulas]]
id = "renta-{YEAR}-cuota-escala-estatal-sobre-base-liquidable-general"
target = "0528"
expression = { op = "lookup_bracket", args = [
    { casilla = "0505" },
    { parameter = "renta-{YEAR}-escala-estatal-base-general" },
] }
rounding = "money-2"
legal_refs = ["ley-35-2006:art-62", "ley-35-2006:art-63"]
source_refs = ["lirpf-cuota-chain-authority"]

# casilla 0530: state cuota for the personal/family minimum
[[revisions."{YEAR}".formulas]]
id = "renta-{YEAR}-cuota-escala-estatal-sobre-minimo-personal-familiar"
target = "0530"
expression = { op = "lookup_bracket", args = [
    { casilla = "0521" },
    { parameter = "renta-{YEAR}-escala-estatal-base-general" },
] }
rounding = "money-2"
legal_refs = ["ley-35-2006:art-62", "ley-35-2006:art-63", "ley-35-2006:art-67"]
source_refs = ["lirpf-cuota-chain-authority"]
```

Each formula gets a `[[...formulas.source_citations]]` block citing
`lirpf-cuota-chain-authority` with required text fragments.

After landing each year's pair, the corresponding entry is removed
from `_PRE_STAGED_PARAMETERS` so the orphan-detection gate stays
strict.

## Rationale

This option was chosen because:

- The bracket data, the runtime op, and the casilla taxonomy are all
  already in place — the only missing piece is the four-line formula
  declaration per casilla per year. Adding the formulas is the
  minimum viable change that closes the orphan-parameter gate at the
  source rather than via allow-listing.
- LIRPF arts. 62-63 are direct legal authority for the formula
  shape. Source citations on the parameter (already declared) and on
  the new formulas (added in this work) anchor every line to legal
  text.
- The AEAT live-oracle and workbook parity gates ensure the formula
  produces the same number AEAT itself produces for the same inputs.

Alternatives considered and rejected:

- **Leave the parameters allow-listed.** Rejected: the IRPF cuota
  chain is legally mandated and end-to-end; allow-listing pre-staged
  data is a tactical hold, not a sustainable destination.
- **Compute the cuota in Python via `read_parameter` rather than via
  a `lookup_bracket` formula.** Rejected: the formula path keeps the
  calculation declarative, anchors it in the source-citation
  pipeline, and lets workbook-parity tests exercise the same
  expression tree the operator sees in the registry.
- **Wire autonomic and state simultaneously.** Rejected: autonomic
  data does not exist yet (CCAA-specific). Sequencing state first
  delivers value sooner and unblocks operators in autonomic-neutral
  cases.

## Consequences

- After this work lands across all six ejercicios, casillas 0528 and
  0530 become computed (no longer manual). Operator UX shifts from
  "type the cuota" to "system computes from base liquidable" — that
  is a desirable simplification but it also means the registry's
  workbook parity gate is the new contract for correctness.
- The `_PRE_STAGED_PARAMETERS` allow-list empties out — confirms the
  orphan-detection gate is doing real work without exemptions.
- The autonomic-scale follow-up becomes the next natural slice.
- A future LIRPF amendment that changes the state progressive scale
  must update the bracket data on the parameter (a TOML edit) and is
  picked up automatically by the formula runtime — no formula
  redeclaration needed.
