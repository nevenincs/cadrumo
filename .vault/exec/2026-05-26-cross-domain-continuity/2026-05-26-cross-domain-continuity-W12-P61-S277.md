---
tags:
  - "#exec"
  - "#cross-domain-continuity"
step_id: S277
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W12.P61.S277 — typed-boundary warmup (_parse_typed_cli_observations)

## Outcome

Replaced `_parse_json_object_options() -> tuple[dict[str, object], ...]` with
`_parse_typed_cli_observations[ObservationT: BaseModel]()` in
`src/aeat/entrypoints/cli/_modelo.py`. This eliminates the first
UNTYPED_BOUNDARY site in the CLI entrypoint layer.

### Key design decisions

- **PEP 695 type parameter syntax** (`[ObservationT: BaseModel]`) per ruff UP047/UP049.
- **`model.model_validate_json(raw)` not `model.model_validate(dict)`**: pydantic's
  JSON-mode coercions handle `string → Decimal` and `string → StrEnum` even when
  the target model declares `strict=True` at the Python-object boundary.
- The two-step approach (parse to dict, check isinstance(dict), then validate_json)
  preserves the non-object early refusal that issues a distinct `json_not_object`
  error before the pydantic path is reached.
- `PerModeloAggregationCommand` is now constructed directly with typed observation
  tuples; the previous `model_validate_json(json.dumps({...}))` indirection is gone.

### New locale key

`cli.app.modelo.aggregate.json_validation_error` added via
`python -m aeat.locales scaffold`; all four locale files audited clean.

### Pre-existing failures noted

Two pre-existing test failures in `test_modelo.py` (unrelated to this step):
- `test_work_calculate_binding_help_points_at_bindings_list` — help text mismatch
- `test_period_token_error_enumerates_modelo_specific_tokens` — period-token ordering

## Commits

- `1515ec548` — W12.P61.S277: replace _parse_json_object_options with typed generic
- `621f8b83b` — W12.P61.S277: regression tests for _parse_typed_cli_observations

## Files changed

- `src/aeat/entrypoints/cli/_modelo.py` — replaced _parse_json_object_options with typed generic; updated aggregate_modelo call site
- `src/aeat/entrypoints/cli/test_modelo.py` — 4 regression tests: round-trip, invalid JSON syntax, non-object JSON, schema violation; added module-level `import json` fixing pre-existing F821
- `src/aeat/locales/en.yml` — `json_validation_error` key (staged as working-tree WIP; locale files excluded from commit to avoid sweeping peer-authored foreign changes)
