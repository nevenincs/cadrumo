---
tags:
  - '#exec'
  - '#modelo-130-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-130-calc-verify-plan]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-rule-delta-reference]]"
---

# `modelo-130-calc-verify` phase-1 step-4: post-Gemini-review extractor registration

Phase-1 step-4 closes a high-priority finding from the Gemini code
review on PR #440: the PR claimed Tier-L coverage for 2024 / 2025 /
2026 declaraciones, but the extractor registry was keyed only on
`(modelo="130", año=2025, revision="2025.01")` — so 2024 and 2026
declaración PDFs raised `NoExtractorRegisteredError` and never
reached the `verify_declaracion` flow.

## Empirical reproduction

```
>>> parse_declaracion(modelo_130_2024_synth.pdf)
NoExtractorRegisteredError: no declaración extractor for ('130', 2024, '2024.01')

>>> parse_declaracion(modelo_130_2026_synth.pdf)
NoExtractorRegisteredError: no declaración extractor for ('130', 2026, '2026.01')
```

The detection step correctly identified the modelo + año + revision
from the synthetic PDF's header (the `Ejercicio:` regex picked up
"2024" / "2026"), but the registry lookup missed because no
extractor class declared those `template_revision` keys.

## Files modified

- `src/aeat/adapters/inbound/declaracion/_extractors/modelo_130_v2025.py` — added two
  thin subclasses (`Modelo130V2024Extractor`,
  `Modelo130V2026Extractor`) that inherit the shared extraction
  logic from `Modelo130V2025Extractor` and pin only their own
  `template_revision` ClassVar. The form layout is identical across
  2024 / 2025 / 2026 (RIRPF art. 110 unchanged per the rule-delta
  manifest), so the regex map + casilla list + structural integrity
  check all carry over verbatim.
- `src/aeat/adapters/inbound/declaracion/_extractors/__init__.py` — registered the
  two new extractor classes alongside the existing 2025 entry.
- `src/aeat/adapters/inbound/declaracion/test_modelo_130_v2025.py`:
  - Refactored the `_generate_pdf` helper to take an explicit
    `año: int = 2025` keyword and a `casilla_values: dict[str, str]`
    positional dict (was `**kwargs` — `ty` flagged the kwargs splat
    when `año` started defaulting to `int`).
  - Added a parametrised `test_per_year_round_trip_resolves_to_correct_template`
    case asserting that 2024 / 2025 / 2026 PDFs each parse cleanly,
    resolve to the right `template_revision`, and round-trip every
    supplied casilla.
- `tests/integration/test_kent_workflows.py` — added a parametrised
  `test_per_year_happy_path_verified` case to
  `TestKentImportsModelo130Declaracion` exercising the full CLI
  flow for each of 2024 / 2025 / 2026. Asserts on stable substrings
  (`Extraction status: COMPLETE`, `Verification status: VERIFIED`,
  `Modelo 130 {ejercicio}Q1`).
- `docs/coverage/modelos.md` — updated the Modelo 130 row's
  declaración-import column to "(2024 + 2025 + 2026, 19-casilla
  full liquidación block #321)" and the provenance line to mention
  the V2024 / V2026 sibling-class registration.
- `.vault/reference/2026-04-27-modelo-130-rule-delta-reference.md` — added a second audit-
  trail row recording the Gemini-driven extractor expansion.

## Tests added

- 3 new parametrised cases in
  `src/aeat/adapters/inbound/declaracion/test_modelo_130_v2025.py::test_per_year_round_trip_resolves_to_correct_template`
  (one per year).
- 3 new parametrised cases in
  `tests/integration/test_kent_workflows.py::TestKentImportsModelo130Declaracion::test_per_year_happy_path_verified`
  (one per year).

## End-to-end verification

```
=== 2024 ===
exit_code: 0
Parsed Modelo 130 2024Q1 declaración (template 2024.01). 19 of 19 casillas extracted.
Extraction status: COMPLETE
Verification status: VERIFIED

=== 2025 ===
exit_code: 0
Parsed Modelo 130 2025Q1 declaración (template 2025.01). 19 of 19 casillas extracted.
Extraction status: COMPLETE
Verification status: VERIFIED

=== 2026 ===
exit_code: 0
Parsed Modelo 130 2026Q1 declaración (template 2026.01). 19 of 19 casillas extracted.
Extraction status: COMPLETE
Verification status: VERIFIED
```

The full Kent success moment ("Kent has the declaración PDF of his
Modelo 130 filing for any supported ejercicio (2024/2025/2026) [...]
the tool returns Extraction status: COMPLETE, Verification status:
VERIFIED") is now achievable end-to-end for all three years.

## Why the form-layout-shared inheritance is correct

A future AEAT layout amendment to Modelo 130 (e.g., a new casilla, a
field reordering, a casilla-id renumbering) would manifest as a new
`Orden HAC/N/YYYY` stamp on the declaración PDF, which the
`detect_template_revision` helper already maps to a
`{año}.orden-{N}` revision string. That revision would NOT match
the `{año}.01` ClassVar on any of the three siblings — the registry
would correctly raise `NoExtractorRegisteredError` and force a new
extractor class for the new layout. The shared inheritance therefore
*enforces* the no-amendment invariant rather than masking it.

## Quality gates

- `just lint` — green.
- `just typecheck` — green (after the `_generate_pdf` signature
  refactor; `ty` rejected the original `**casilla_values: str`
  splat once `año: int` was introduced).
- `just test` — 3741 passed (up from 3735).
- `just hooks` — green.

## Out of scope

This step does not introduce per-year *extractor logic* divergence
— if the form layout shifts in a future year, a follow-up issue will
ship a per-year layout class. The current siblings exist to register
the (modelo, año, revision) triples the synthetic generator emits
for 2024 / 2026, no more.
