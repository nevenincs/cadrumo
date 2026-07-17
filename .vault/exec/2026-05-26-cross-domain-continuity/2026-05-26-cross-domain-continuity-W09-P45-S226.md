---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S226'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R7-D Pere observation calculation-result casilla labels remain in Spanish even with output-language ca

## Scope

- `investigate whether registry casilla.label fields are localised and whether the CLI emitter consults the active profile language when rendering casilla rows`
- `decide whether to translate labels or document the legal-Spanish convention explicitly to operators`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Ground the defect with `vaultspec-rag` and trace the mismatch between localized `modelo casillas` payloads and Spanish-only result-summary rows.
- Carry registry `localized_labels` through application result-summary rows while preserving the official Spanish `label` fallback.
- Render result-summary text and JSON display labels through the active `output_language`.
- Add focused isolated-storage coverage with a real Modelo 130 work unit, registry-grounded observations, and Catalan result-summary rendering.

## Outcome

- Result-summary text output now displays Catalan registry labels such as `Rendiment net` when the active output language is Catalan.
- JSON result-summary rows expose the active display `label` plus the full `localized_labels` map for machine consumers.
- Official Spanish labels remain the application fallback when no localized label is available.

## Notes

- Validation: `uv run --no-sync ruff check src/aeat/application/modelo/_result_summary.py src/aeat/entrypoints/cli/_modelo_rendering.py src/aeat/entrypoints/cli/_modelo_revision_payload_parts.py src/aeat/entrypoints/cli/tests/test_modelo_result_summary_labels.py`; `uv run --no-sync pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_modelo_result_summary_labels.py -q`.
- The broad CLI result-summary test file currently fails before calculation because its profile-create setup returns an internal-error envelope; S226 uses a focused isolated-storage renderer test to cover the repaired boundary without inheriting that unrelated fixture failure.
- A blocking package import failure from the participation-index repository relocation was fixed separately before S226 verification.
- Code review found no scoped findings; residual risk is limited to missing full-envelope JSON and fallback-language coverage.
