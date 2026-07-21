---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S358'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R9-TOMAS-HIGH royalties SGAE guidance gap

## Scope

- `the CLI accepts both actividad_economica and capital_mobiliario classifications for royalty income without explaining the legal distinction (Art. 25.4 LIRPF vs rendimiento de actividad económica habitual)`
- `add wizard prompt or ledger classify --help text explaining when to use which`
- `src/aeat/application/wizard/`

## Description

- Ground S358 with the required code RAG query, then inspect the live `ledger classify` option owner, IRPF category catalogue, aggregation behaviour, and existing CLI help regression.
- Keep the fix to guidance text on the existing `cli.ledger.classify.irpf_category_help` locale leaf rather than adding automatic royalty classification logic.
- Update en/es/ca/hu locale leaves through `python -m aeat.locales set`, preserving `actividad_economica` and rent-withholding guidance while adding the Art. 25.4 vs Art. 27 royalty/SGAE distinction.
- Extend the real `aeat app ledger classify --help` regression so the help output continues to expose accepted ids and now also exposes the royalty activity/capital distinction.

## Outcome

- `aeat app ledger classify --help` now tells operators that royalties/SGAE receipts may be capital mobiliario under Art. 25.4 when the taxpayer is not the author, and that `actividad_economica` should be used only for own-account activity under LIRPF Art. 27.
- No classification heuristics or wizard flow changes were added; the CLI still leaves the legal treatment to the operator.
- The live code inspection found `capital_mobiliario` as a profile/modelo income concept, not as a public ledger IRPF category id, so the help avoids advertising it as a direct `--irpf-category` value.

## Notes

- Validation: `uvx vaultspec-rag search "royalty income actividad economica capital mobiliario ledger classify help SGAE" --type code --timeout 30 --max-results 8` passed before edits.
- Validation: `uv run --no-sync pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_ledger_ux_defect_cluster.py::test_classify_help_points_irpf_category_to_categories_catalogue -q` passed.
- Validation: `uv run --no-sync ruff check src/aeat/entrypoints/cli/tests/test_ledger_ux_defect_cluster.py` passed.
- Validation: `uv run --no-sync python -m aeat.locales scaffold --check` passed for ca/en/es/hu.
- Validation: `uv run --no-sync python -m aeat.locales audit` passed for ca/en/es/hu.
- Review: no implementation findings; the S358 audit artifact could not be appended because `.vault/audit/2026-07-02-cross-domain-continuity-audit.md` is existing untracked peer WIP and `vaultspec-core vault add audit --feature cross-domain-continuity --title S358-royalty-guidance-review --dry-run` refuses the occupied path without `--force`.
- Note: `.vault/exec/2026-05-26-cross-domain-continuity/` already contained unrelated peer WIP before this record was added; this step touched only the new S358 record in that directory.
