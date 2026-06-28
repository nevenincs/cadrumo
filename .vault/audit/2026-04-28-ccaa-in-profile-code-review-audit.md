---
tags:
  - '#audit'
  - '#ccaa-in-profile'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - '[[2026-04-28-ccaa-in-profile-research]]'
  - '[[2026-04-28-ccaa-in-profile-adr]]'
  - '[[2026-04-28-ccaa-in-profile-plan]]'
  - '[[2026-04-28-ccaa-in-profile-summary-exec]]'
---

# `ccaa-in-profile` Code Review

Status: ACCEPTED AFTER REVISION

## Findings

CCAA-001 | HIGH | RESOLVED | New user-facing profile/M100 strings bypass the trilingual output path

The ADR requires user-facing strings to pass through the trilingual `Translatable` pattern, but several new strings were hard-coded. The M100 import path, profile CLI help/reference text, and setup tax-residence prompt now use `Translatable` values with Spanish, English, and Hungarian entries. Targeted CLI/setup/integration tests pass after the revision.

CCAA-002 | MEDIUM | ACCEPTED | `uv.lock` contains bootstrap dependency upgrades

The lockfile changed package versions for dependencies that are not part of the tax-residence profile implementation: `mako`, `transformers`, `ty`, and `vaultspec-rag`. This is retained because issue #452 explicitly required the bootstrap sequence `uv sync --all-groups --upgrade`, `uv lock --upgrade`, and `uv run vaultspec-core install --upgrade` before implementation. The refreshed lockfile has been verified with lint, typecheck, test, coverage, hooks, and ruleset citation audit.

CCAA-003 | LOW | RESOLVED | Public-facing references still point at private ruleset internals

The new `aeat.domain.profile` package correctly re-exports `CCAA`, but changed public-facing surfaces still referenced private formula internals. The profile CLI, setup code/tests, integration tests, and concept documentation now import or document the CCAA type through `aeat.domain.profile`. The integration test still imports the private autonomic calculator for a focused expected-value assertion because that calculator is the M100 ruleset behavior under test, not the new public profile surface.

## Invariant Audit

- Strict frozen Pydantic v2 model using existing CCAA enum: PASS. `KentTaxResidence.model_config` and `ResidenceChange.model_config` include `strict=True`, `frozen=True`, and `extra='forbid'`; `src/aeat/domain/profile/__init__.py` consumes the existing `CCAA` enum.
- Local-state Path A JSON persistence with no #216 storage dependency: PASS. `src/aeat/domain/profile/_storage.py` uses config-directory JSON, same-directory temp files, and `os.replace`; no `aeat.adapters.persistence.storage`, SQLAlchemy, or Alembic dependency was introduced.
- No namespace pollution with existing profile surfaces: PASS. New code is isolated under `src/aeat/profile` and `src/aeat/entrypoints/cli/profile`; existing financial, browser, and category profile surfaces were not extended.
- Foral-regime error path for `pais-vasco` and `navarra`: PASS. `parse_tax_region` rejects the foral aliases with `ForalRegimeError`, and tests cover `pais-vasco`, `país_vasco`, and `navarra`.
- M100 wiring and no-profile REFUSED path: PASS. Borrador and Modelo 100 declaración import paths call `require_tax_residence`; integration coverage asserts the missing-profile REFUSED suggestion.
- Trilingual strings: PASS. See CCAA-001 remediation.
- ErrorCode registration for new errors: PASS. `TaxResidenceProfileError`, `ProfileNotConfiguredError`, and `ForalRegimeError` are registered in `src/aeat/core/errors/_registry.py`.
- Public API imports from `aeat.domain.profile` and `aeat.entrypoints.cli` only: PASS for the profile CCAA surface; see CCAA-003 remediation.
- Test markers: PASS. New modules use module-level `pytestmark`, and `tests/test_marker_integrity.py` passed in the full test run.
- No source/docstring wave or numbered-cycle wording: PASS for changed source and docstrings. Existing unrelated documentation still contains older cycle terminology, but the changed source/docstring surface for #452 did not introduce it.
- Lint/typecheck/test/hooks green: PASS. `just lint`, `just typecheck`, `just test`, and `just hooks` all passed on 2026-04-29.

## Changed Files Audited

Audited modified tracked files: `docs/coverage/kent-capabilities.md`, `env/.env.example`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py`, `src/aeat/entrypoints/cli/__init__.py`, `src/aeat/entrypoints/cli/filing/__init__.py`, `src/aeat/entrypoints/cli/test_json_schema_conformance.py`, `src/aeat/config.py`, `src/aeat/core/errors/_registry.py`, `src/aeat/domain/schema/test_cache.py`, `src/aeat/domain/schema/test_models.py`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/_declarations.py`, `src/aeat/application/setup/_env_writer.py`, `src/aeat/application/setup/_models.py`, `src/aeat/application/setup/_wizard.py`, `src/aeat/application/setup/test_cli.py`, `src/aeat/application/setup/test_env_writer.py`, `src/aeat/application/setup/test_models.py`, `src/aeat/application/setup/test_verifier.py`, `src/aeat/application/setup/test_wizard.py`, `tests/integration/test_kent_workflows.py`, and `uv.lock`.

Audited new untracked files: `.vault/adr/2026-04-28-ccaa-in-profile-adr.md`, `.vault/exec/2026-04-28-ccaa-in-profile/2026-04-28-ccaa-in-profile-summary.md`, `.vault/plan/2026-04-28-ccaa-in-profile-plan.md`, `.vault/research/2026-04-28-ccaa-in-profile-research.md`, `docs/concepts/tax-residence.md`, `src/aeat/entrypoints/cli/profile/__init__.py`, `src/aeat/entrypoints/cli/profile/test_cli.py`, `src/aeat/domain/profile/__init__.py`, `src/aeat/domain/profile/_errors.py`, `src/aeat/domain/profile/_storage.py`, `src/aeat/domain/profile/test_errors.py`, `src/aeat/domain/profile/test_model.py`, and `src/aeat/domain/profile/test_storage.py`.

## Verification

- `git diff --check`: PASS.
- `just lint`: PASS.
- `just typecheck`: PASS.
- `just test`: PASS, 4156 passed, 14 skipped, 24 deselected, 26 warnings.
- `just hooks`: PASS.
- Post-revision `just lint`: PASS.
- Post-revision `just typecheck`: PASS.
- Post-revision focused tests (`src\aeat\profile`, `src\aeat\cli\profile`, `src\aeat\setup`, `tests\integration\test_kent_workflows.py`): PASS, 119 passed.
- Post-revision `git diff --check`: PASS.
- Post-revision `just test`: PASS, 4156 passed, 14 skipped, 24 deselected, 26 warnings.
- Post-revision `just test-cov`: PASS, total coverage 81.48%, above the 60% floor.
- Post-revision `just hooks`: PASS.
- Post-revision `uv run aeat audit rulesets citations`: PASS, aggregate 232/232 computed casillas with citations, 100.00% coverage.

## Residual Risk

The review did not exercise live AEAT services. The M100 profile integration is covered by synthetic PDFs and local CLI tests, which is appropriate for this no-live-write feature, but it does not prove behavior against future AEAT PDF layout drift. The full test run still includes 14 pre-existing skipped tests; no new skip or xfail was added for #452.
