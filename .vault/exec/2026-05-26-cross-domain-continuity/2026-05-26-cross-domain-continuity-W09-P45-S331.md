---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S331'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R9-ZSOFIA-D Kv format error raw technical English string surfaces during work verify error path

## Scope

- `locate and route via tr() with locale-prose explanation of what KV format is`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Ground the defect with `vaultspec-rag` and trace the shared modelo KEY=VALUE parser plus the verify finding that emitted raw English `--binding KEY=VALUE` guidance.
- Route the cross-period not-applicable verify finding through `tr()` with locale prose explaining `KEY=VALUE`.
- Expand the shared modelo work malformed KEY=VALUE parser defaults and the four locale catalogues for generic and `--row` malformed specs.
- Add real-behavior regression coverage for the verify finding locale path and the CLI malformed `--binding` path.

## Outcome

- `modelo work verify` cross-period not-applicable advisories no longer emit the raw English KEY=VALUE guidance in non-English output.
- Malformed modelo work KEY=VALUE specs now explain that the key or binding id is placed to the left of one equals sign and the value on the right.
- Locale scaffold and audit both pass for `en`, `es`, `ca`, and `hu`.

## Notes

- Validation: `uv run --no-sync python -m aeat.locales scaffold --check`; `uv run --no-sync python -m aeat.locales audit`; `uv run --no-sync ruff check src/aeat/application/modelo/_verification_cross_period.py src/aeat/application/modelo/tests/test_cross_period_finding_legal_grounding.py src/aeat/application/modelo/tests/test_cross_period_modelo_not_applicable_localization.py src/aeat/entrypoints/cli/_modelo_cli_support.py src/aeat/entrypoints/cli/tests/test_modelo_kv_format_localization.py`; `uv run --no-sync pytest src/aeat/application/modelo/tests/test_cross_period_modelo_not_applicable_localization.py src/aeat/application/modelo/tests/test_cross_period_finding_legal_grounding.py -q -m unit`; `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_modelo_kv_format_localization.py -q -m "integration and hex_entrypoint"`.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_modelo_kv_format_localization.py -q` was deselected by the repository default `-m unit` filter; rerun with the integration marker passed.
- Review noted low-severity locale YAML scalar reflow outside the new S331 keys. The changes were retained because locale leaves were updated only through the sanctioned `aeat.locales set` CLI, whose serializer owns that formatting; the semantic locale changes remain limited to the intended keys.
