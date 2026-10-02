---
tags:
  - '#exec'
  - '#tui-profile-setup-ux'
date: '2026-10-02'
modified: '2026-10-02'
body_schema: 'body-v2'
body_hash: 'sha256:7d6af4b45c32bd01d712aafaceca77cac7a685032fbe4cce6c041a5cfbf2cca9'
related:
  - "[[2026-10-02-tui-profile-setup-ux-plan]]"
---

# `tui-profile-setup-ux` ledger

## Changes

- `S01` `M` `src/cadrumo/entrypoints/tui/profile/overview.py`
- `S01` `A` `src/cadrumo/entrypoints/tui/profile/setup_journey.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/secret/registration.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/tests/test_manager_onboarding.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/tests/test_manager_required_field_refusal.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/tests/test_manager_masked_required_field.py`
- `S01` `M` `src/cadrumo/locales/ca/flows.yml`
- `S01` `M` `src/cadrumo/locales/en/flows.yml`
- `S01` `M` `src/cadrumo/locales/es/flows.yml`
- `S01` `M` `src/cadrumo/locales/hu/flows.yml`
- `S01` `verify:` `uv run --no-sync pytest -q -n 4 -o addopts= --tb=short -m 'unit or integration' $profileTests` -> `pass`
- `S01` `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/tui/profile src/cadrumo/entrypoints/tui/secret/registration.py src/cadrumo/entrypoints/tui/tests/test_manager_onboarding.py src/cadrumo/entrypoints/tui/tests/test_manager_required_field_refusal.py src/cadrumo/entrypoints/tui/tests/test_manager_masked_required_field.py` -> `pass`
- `S01` `verify:` `uv run --no-sync ruff format --check src/cadrumo/entrypoints/tui/profile src/cadrumo/entrypoints/tui/secret/registration.py src/cadrumo/entrypoints/tui/tests/test_manager_onboarding.py src/cadrumo/entrypoints/tui/tests/test_manager_required_field_refusal.py src/cadrumo/entrypoints/tui/tests/test_manager_masked_required_field.py` -> `pass`
- `S01` `verify:` `uv run --no-sync ty check (changed TUI paths)` -> `pass`
- `S01` `verify:` `uv run --no-sync python -m dev.locales status --json --check` -> `fail`
- `S01` `verify:` `uv run --no-sync vaultspec-core vault check all` -> `fail`
- `S02` `M` `dev/tui/harness/surfaces.py`
- `S02` `A` `dev/tui/harness/profile_fixtures.py`
- `S02` `A` `dev/tui/harness/tests/test_profile_fixtures.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/profile/overview.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/secret/registration.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/tests/test_manager_onboarding.py`
- `S02` `M` `src/cadrumo/locales/ca/flows.yml`
- `S02` `M` `src/cadrumo/locales/en/flows.yml`
- `S02` `M` `src/cadrumo/locales/es/flows.yml`
- `S02` `M` `src/cadrumo/locales/hu/flows.yml`
- `S02` `A` `.vault/audit/2026-10-02-tui-profile-setup-ux-audit.md`
- `S02` `verify:` `uv run --no-sync pytest -q -n 4 -o addopts= --tb=short -m 'unit or integration' $profileTests dev/tui/harness/tests/test_profile_fixtures.py dev/tui/tests/test_tui_visual_inventory.py dev/tui/tests/test_tui_review_elements.py dev/tui/tests/test_tui_surface_identity_resolution.py` -> `pass`
- `S02` `verify:` `uv run --no-sync pytest -q -n 2 -o addopts= --tb=short -m 'unit or integration' src/cadrumo/entrypoints/tui/profile/tests` -> `pass`
- `S02` `verify:` `uv run --no-sync ruff check (six S02 Python paths)` -> `pass`
- `S02` `verify:` `uv run --no-sync ruff format --check (six S02 Python paths)` -> `pass`
- `S02` `verify:` `uv run --no-sync ty check (six S02 Python paths)` -> `pass`
- `S02` `verify:` `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-10-02-tui-profile-setup-ux-plan.md` -> `pass`
- `S02` `verify:` `uv run --no-sync python .tmp-tui-visual-inventory/profile_capture_run.py es` -> `pass`
- `S02` `verify:` `uv run --no-sync python .tmp-tui-visual-inventory/profile_capture_run.py en` -> `pass`
- `S02` `verify:` `uv run --no-sync python .tmp-tui-visual-inventory/profile_capture_run.py ca` -> `pass`
- `S02` `verify:` `uv run --no-sync python .tmp-tui-visual-inventory/profile_capture_run.py hu` -> `pass`
- `S02` `verify:` `final profile capture matrix, source fingerprints, artifact digests and served HTTP images` -> `pass`
- `S02` `verify:` `uv run --no-sync python -m dev.locales status --json --check` -> `fail`

## Notes

- `S01` 86 profile and registration tests pass. Global locale and vault gates retain unrelated baseline failures; the scoped feature check is clean. The setup translations are enrolled in all four locales with no missing keys or placeholder mismatches.
- `S02` Global locale status retains unrelated baseline inventory and spelling-tool failures; all four required catalogues are complete, placeholders match, and no changed setup or registration key has a finding. Final review is PASS. PNGs are gitignored review artifacts in four named runs because a separate renderer owns current.
