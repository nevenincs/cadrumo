---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:bdfdf9d579be09e8c63e5d31964bd82ff9ad454d488b530dce31e4e5973a97b6'
step_id: 'S235'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R7-ANNA-D4 expand wizard non-TTY refusal message to list the minimum required flags for one-shot profile creation

## Scope

- `currently only --tax-id NIF mentioned but entity-type irpf-income-categories tax-residence-ccaa are also required`
- `src/aeat/application/wizard/`

## Description

- Ground the wizard no-console refusal path with `uvx vaultspec-rag search` and the live `_run_full_flow`, locale, filing-baseline, and profile lifecycle test surfaces.
- Expand the no-TTY `profile create NAME` recovery copy in `en`, `es`, `ca`, and `hu` to advertise a resident IRPF natural-person one-shot command with `--tax-id`, `--entity-type natural_person`, `--irpf-income-categories actividad_economica`, `--tax-residence-ccaa madrid`, `--name`, and `--surnames`.
- Strengthen the real CLI regression so it asserts the exact advertised command and then runs the same flag set with concrete values to prove profile creation succeeds.
- Preserve the separate `profile create NAME --quiet` missing-required-flags refusal path and its internal-token leak assertions.
- Resolve the first review's blocking finding that the advertised command still omitted the filing-baseline identity fields.

## Outcome

Closed `W09.P45.S235`. The non-interactive no-console profile-create refusal now gives operators a one-shot command that is complete enough to create the default resident IRPF natural-person profile shape, and the regression proves that command path against the real CLI.

Validation passed:

- `uv run --no-sync pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py::test_config_profile_create_bare_name_refusal_names_both_recovery_paths src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py::test_config_profile_create_quiet_without_flags_names_the_missing_flags -q`
- `uv run --no-sync python -m aeat.locales audit`
- `uv run --no-sync python -m aeat.locales scaffold --check`
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py`
- `git diff --check -- src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/ca.yml src/aeat/locales/hu.yml src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py`

## Notes

The first review rejected the initial copy-only patch because the advertised command omitted `--name` and `--surnames`; the real CLI then refused with filing-baseline missing flags. The accepted patch resolves that by aligning the no-console hint with `missing_filing_baseline_flags`.

Residual risk is limited to non-English text not having exact rendered-command integration assertions. The locale scaffold and audit checks passed for all four locale files.
