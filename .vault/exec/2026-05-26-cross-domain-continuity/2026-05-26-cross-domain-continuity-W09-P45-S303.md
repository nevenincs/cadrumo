---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:348b0119baca7dce389b79eaf78729079c71481f897024c1176ecc3cfe3d5b83'
step_id: 'S303'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R8-ROSA-G when profile create rejects a combination of flags surface the SPECIFIC field that failed validation not a generic La entrada del comando no supero la validacion message

## Scope

- `Rosa hit this with taxation-type 2 plus family-minor-children-in-unit and could not identify which pair conflicted`
- `src/aeat/entrypoints/cli/_config/__init__.py`

## Description

- Ground S303 with RAG against the cross-domain plan row, the current profile-create wizard command path, and the existing ledger validation-detail refusal pattern.
- Keep the underlying `SetupAnswers` validation rule unchanged.
- Catch wizard persistence-path `ValidationError` values before they reach the generic CLI validation boundary.
- Format pydantic validation entries as operator-facing CLI flag details by mapping wizard question identifiers to their `--flag` names.
- Add localized profile-detail validation messages in English, Spanish, Catalan, and Hungarian.
- Add an integration regression proving joint-taxation profile create names `--spouse-tax-id` and `--taxation-type` instead of the generic command-input validation boundary.
- Run a scoped code review after implementation; the reviewer reported no findings.

## Outcome

S303 is closed. `config profile create` now surfaces the concrete flag-level cause for the Rosa joint-family validation case rather than the generic `La entrada del comando no superó la validación` boundary text. The verified output names `--spouse-tax-id` and `--taxation-type`, omits `config repair`, and does not expose a traceback.

## Notes

Validation:

- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py::test_config_profile_create_joint_family_validation_names_failing_flags -q` passed.
- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py -q` passed with 35 tests.
- `uv run --no-sync ruff check src/aeat/application/wizard/_commands.py src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py` passed.
- `uv run --no-sync python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run --no-sync python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `git diff --check` passed for the S303 path set, with only existing CRLF normalisation warnings on touched files.

Notes:

- A direct isolated CLI probe returned `Invalid value for '--spouse-tax-id': The profile details are invalid: --spouse-tax-id is required when --taxation-type is joint (--taxation-type='2')`.
- Review agent Kepler reported no findings. Residual risk is limited to other unexercised wizard `ValidationError` shapes that will now use the same generic formatter.
