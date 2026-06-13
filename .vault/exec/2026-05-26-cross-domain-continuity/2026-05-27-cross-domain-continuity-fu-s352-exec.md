---
step_id: FU-S352
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-27-cross-domain-continuity-W09-P41-S352]]"
  - "[[2026-05-27-cross-domain-continuity-w09-p41-s352-review-exec]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# FU-S352: route engine-layer seed_hint through tr()

## Outcome

Closed three follow-up findings from the S352 code review (LOCALE-001 MEDIUM, LOCALE-002 LOW, TEST-001 LOW).

## Commit

`de6641b0d` — FU-S352: route engine-layer ModeloAggregationBindingError through tr()

## Changes

- `src/aeat/application/modelo/_actions.py`: Replaced raw English `seed_hint` string concatenated into `ModeloAggregationBindingError.args[0]` with `translated_message="errors.error.error_modelo_aggregation_binding"` + `suggestion="aeat app modelo iva-wallet seed"` (conditional). The `resolve_error_message` path now reaches `tr(message_key)` instead of short-circuiting on `args[0]`. The `get_error_suggestion` path surfaces the seed command as a `-> Run` hint in the CLI output.

- `src/aeat/entrypoints/cli/test_iva_wallet_inspector.py`: Captured the first `_RUNNER.invoke` result in `test_cli_seed_verb_refuses_duplicate` and added `assert first_result.exit_code == 0` to ensure the duplicate-refusal assertion exercises the conflict path rather than the NIF-not-found path.

- `.vault/exec/2026-05-26-cross-domain-continuity/2026-05-27-cross-domain-continuity-W09-P41-S352.md`: Corrected locale key count from 7 to 10 with explicit key names.

## Gates

- 13/13 tests pass (all iva_wallet_inspector)
- ruff: 0 errors
- pyright: 0 errors on modified files (1 pre-existing unrelated warning)
- locale audit: no change (no new keys — hint is now surfaced via existing `ErrorCode.suggestion` infrastructure)
