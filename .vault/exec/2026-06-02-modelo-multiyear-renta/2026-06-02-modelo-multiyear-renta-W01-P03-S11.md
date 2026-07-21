---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# add the ADVISORY work-calculate banner naming the unauthorized state for unauthorized-but-has-engine modelos (vaultspec-standard-executor)

## Scope

- `src/aeat/entrypoints/cli/tests/test_modelo_authorization_advisory_banner.py`
- `.vault/plan/2026-06-02-modelo-multiyear-renta-plan.md`
- `.vault/index/modelo-multiyear-renta.index.md`

## RAG grounding

- `uvx vaultspec-rag search "modelo work calculate unauthorized backend advisory authorization_state notices" --type code`
- `uvx vaultspec-rag search "modelo multiyear renta W01 P03 S11 unauthorized backend advisory calculate" --type vault --doc-type plan,exec`

The code search landed on `src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py`, specifically `_work_calculate_authorization_output`, and on the application-side `authorization_advisory_for_modelo` derivation in `src/aeat/application/modelo/_calculate_input.py`. The vault search confirmed this row was still open in the `modelo-multiyear-renta` plan and that S09/S10 already had exec records.

## Description

- Added a real-behavior CLI integration ratchet for Modelo 117, an unauthorized modelo that declares a real `calculation` surface.
- The test seeds a real active encrypted bucket through `UserProfileLifecycleRepository`, creates a real Modelo 117 work unit, and drives `app modelo work calculate` through `invoke_cached_cli`.
- The text-mode assertion proves calculation succeeds and emits `authorization_state` plus the English unauthorized advisory instead of refusing solely because the derived authorization state is unauthorized.
- The JSON assertion proves the success envelope carries notice code `modelo.work.calculate.unauthorized_backend`, warning severity, and context `authorization_state`.
- Left production code unchanged because the real CLI probe and the new test confirmed the advisory is already emitted.

## Outcome

- `uv run pytest src/aeat/entrypoints/cli/tests/test_modelo_authorization_advisory_banner.py -m integration -q --tb=short`: 1 passed.
- `uv run ruff check src/aeat/entrypoints/cli/tests/test_modelo_authorization_advisory_banner.py`: passed.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py::test_work_calculate_confirms_the_draft_was_saved -m integration -q --tb=short`: 1 passed.
- `uv run vaultspec-core vault feature index --feature modelo-multiyear-renta`: regenerated `.vault/index/modelo-multiyear-renta.index.md`.
- `uv run vaultspec-core vault plan check .vault/plan/2026-06-02-modelo-multiyear-renta-plan.md`: passed with existing PLAN022 monotonic-order warning.
- `uv run vaultspec-core vault check features --feature modelo-multiyear-renta`: clean.
- `uv run vaultspec-core vault check frontmatter --feature modelo-multiyear-renta`: clean.
- `uv run vaultspec-core vault check dangling --feature modelo-multiyear-renta`: clean.

## Residuals

- The current machine contract uses the enum value `unauthorized` in `result.authorization_state` and notice context; the human advisory text independently names `UNAUTHORIZED`.
- `uv run vaultspec-core vault check all --feature modelo-multiyear-renta` is blocked by 29 pre-existing `feature-rename-integrity` errors in unrelated exec folders; this row's feature/frontmatter/dangling checks are clean.
- Full repository tests were not run because the shared worktree carries broad unrelated WIP.
