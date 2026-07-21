---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S09'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Author the modelo-151-base-liquidable-implica-cuota-integra ADVISORY predicate implies_nonzero(["impatriado.base-liquidable-general", "impatriado.cuota-integra-general"]) with legal_refs ley-35-2006:art-93, creating the verification_expectations directory on the 2015-y-siguientes revision

## Scope

- `src/aeat/_data/registry/aeat/modelos/151/revisions/2015-y-siguientes/verification_expectations/0001-verification_predicates.toml`

## Description

- Confirmed `impatriado.base-liquidable-general` and `impatriado.cuota-integra-general` exist as M151 casillas and that the cuota is formula-derived from the base via `lookup_bracket` against the `modelo-151.escala-cuota-integra-general` table (`formulas/0001-formulas.toml`, formula id `modelo-151-cuota-integra-general`), confirming the implication is formula-defended rather than operator-skippable.
- Confirmed `ley-35-2006:art-93` is already authored in the legal catalogue (`legal/irpf-impatriados.toml`) with `review_status = "reviewed"` and a `corpus_ref` resolving to bundled BOE text; no new legal-catalogue authoring was needed.
- Created the `verification_expectations/` directory under `2015-y-siguientes` (previously absent) and authored `0001-verification_predicates.toml` with one predicate: `predicate_id = "modelo-151-base-liquidable-implica-cuota-integra"`, `expression = 'implies_nonzero(["impatriado.base-liquidable-general", "impatriado.cuota-integra-general"])'`, `finding_kind = "ADVISORY"`, `legal_refs = ["ley-35-2006:art-93"]`, mirroring the M200/M131 worked pattern.

## Outcome

The registry loads the new fragment without a validation error: `uv run --no-sync pytest src/aeat/domain/calculations/registry/tests/test_modelo_151_registry.py -q` passes (see S10 record for the dedicated registry-shape assertion). A broader registry-build pass over `validat`-keyed tests under `src/aeat/domain/calculations/registry` (82 tests, including the new M151 predicate) passed with zero failures.

## Notes

No incidents. The `verification_expectations` directory did not previously exist on the 2015-y-siguientes revision (per the ADR's "creating the verification_expectations directory" framing); created fresh, no other files in that revision were touched.
