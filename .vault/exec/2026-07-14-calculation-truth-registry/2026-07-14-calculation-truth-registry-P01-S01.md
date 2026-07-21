---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S01'
related:
  - "[[2026-07-14-calculation-truth-registry-plan]]"
---

# Author the Modelo 131 2024 modulos-engine formula, parameter, and casilla fragments mirroring the 2025 and 2026 revisions

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/131/revisions/2024/`

## Description

- Diff the 2024/2025/2026 revision fragment trees to confirm the exact gap: 2024 lacked `casillas/0003-modulos-engine.toml`, `formulas/0003-modulos-engine.toml`, and `parameters/0002-modulos-coeficientes.toml`.
- Cross-check the bundled `corpus/normatives/html/orden-hfp-1359-2023.html` (the 2024 filing year's applicable Orden de modulos, BOE-A-2023-25882) against `orden-hac-1347-2024.html` (the 2025 Orden already grounding the 2025 fragments) and confirm every currently-tabled activity's euro-per-unit rendimiento figure, the reduccion general (5 por ciento), the incentivos-al-empleo coeficiente (0.40) and tramos table, the indice corrector de exceso (1.30), and its eight tabled cuantias are byte-identical between the two Ordenes.
- Cross-check every required grounding phrase against the bundled `corpus/manuals/renta/2024/part1/source.pdf.extracted.md` (AEAT Manual practico de Renta 2024) via the project's own `normalise_corpus_text` evidence-matching function, not raw string containment.
- Author `casillas/0003-modulos-engine.toml`, `formulas/0003-modulos-engine.toml`, and `parameters/0002-modulos-coeficientes.toml` for the 2024 revision by transforming the 2025 fragments: retarget every `orden-hac-1347-2024` legal_ref to `orden-hfp-1359-2023`, retarget `aeat-renta-2025-manual-parte1` to `aeat-renta-2024-manual-parte1`, retarget every id/date literal from 2025 to 2024, and correct the two "ejercicio anterior" year references embedded in casilla labels (2024 to 2023).
- Add the eight missing `orden-hfp-1359-2023` legal catalogue entries (`da-1`, `instruccion-2-2-a`, `instruccion-2-2-b`, `instruccion-2-3-b-3`, `anexo-ii-instruccion-2-3-incompatibilidades`, `anexo-ii-instruccion-2-3-b-1`, `anexo-ii-instruccion-2-3-b-2`, `anexo-ii-instruccion-2-3-b-4`) to `legal/irpf.toml`, each verified against the bundled Orden HTML text.
- Discover, via full content-level diffing (not file-count comparison), that the 2024 revision's `verification_expectations/0002-verification_predicates.toml`, `verification_expectations/0003-reconcile-when-present.toml`, `completeness_manifest/0001-completeness_manifest.toml`, and `constructs/0001-constructs.toml` also lacked the modulos-engine casilla/formula/parameter enrolments the 2025 revision already carries, and extend all four to match.
- Load the 2024 registry snapshot and confirm all 19 modulos casillas resolve; run `pytest --collect-only -q` (clean) and the full M131 test surface (175 tests green).
- Fix two test-expectation gaps a full registry-tests-directory run surfaced: `test_committed_modelo_131_registry_snapshot_calculates_objective_estimation_totals` (hardcoded 2025/2026-only expected-entries set) and `test_calculation_completeness_manifest_legal_refs_match_calculation_closure` (completeness_manifest's own `legal_refs` field had not been extended to match the construct).

## Outcome

The Modelo 131 2024 revision now carries the full four-fase estimacion-objetiva modulos engine (rendimiento neto previo, minorado, de modulos, de la actividad) at parity with the 2025/2026 revisions, grounded in Orden HFP/1359/2023 rather than copy-pasted forward from 2025. Registry loads clean (`bundled_authority().snapshot(Modelo.M131, filing_year=2024, period="1T")` resolves 35 casillas, 13 formulas, 19 of them modulos-prefixed). `uv run --no-sync pytest --collect-only -q` collects 12930 tests cleanly. The full `src/cadrumo/domain/calculations/registry/tests/` directory, the M131-specific test surface (175 tests), and the broader `application/modelo`, `application/calculations`, and `adapters/inbound/declaracion` test directories are green (one registry-directory-changed race and one loader-cache race reproduced only under `-n auto` parallel xdist, both confirmed non-regressions by sequential re-run per `aeat-local-execution`).

## Notes

No legal-grounding gaps: every numeric figure in the new fragments (module coefficients, reduccion general, empleo coeficiente/tramos, indice de exceso, cuantias) was independently cross-checked against the bundled Orden HTML corpus and the bundled AEAT Manual de Renta 2024 PDF extraction, not copied from the 2025 fragments without re-verification. The bundled corpus for the 2024 Orden (`orden-hfp-1359-2023.html`) was already present in the repository (no new corpus acquisition needed).
