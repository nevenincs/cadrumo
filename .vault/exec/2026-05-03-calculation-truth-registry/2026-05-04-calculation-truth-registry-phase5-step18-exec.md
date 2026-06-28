---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase5` `step18`

Replaced declaration verification's removed formula-source placeholder with
registry snapshot execution and aligned CLI tests with the current authority
registry behavior.

- Modified: `src/aeat/application/verification/_verify.py`
- Modified: `src/aeat/application/verification/_schema.py`
- Modified: `src/aeat/application/verification/_errors.py`
- Modified: `src/aeat/application/verification/__init__.py`
- Modified: `src/aeat/application/verification/test_verify.py`
- Modified: `src/aeat/entrypoints/cli/filing/__init__.py`
- Modified: `src/aeat/entrypoints/cli/filing/test_filing_cli.py`
- Modified: `src/aeat/entrypoints/cli/registry.py`
- Modified: `src/aeat/entrypoints/cli/test_user_cli_surface.py`
- Created: `src/aeat/application/verification` registry-backed behaviour tests
- Created: `.vault/audit/2026-05-04-calculation-truth-registry-phase5-step18-review.md`

## Description

Declaration verification now loads a validated registry snapshot for the parsed
filing, maps filing periods to registry period selectors, executes the registry
formula runtime, compares decimal extracted casillas against computed values,
and emits registry snapshot ids in verdict records. Formula-source placeholders
and `ruleset_id` verdict state were removed from the verification boundary.

The missing-registry path now fails hard with `VerificationError`. The previous
`UNVERIFIABLE` status and unverifiable verdict helper were removed so unsupported
modelos cannot become soft verification states. The filing CLI catches the
verification error and reports it as an invalid operator input while preserving
the fail-closed behavior.

The filing CLI no longer builds synthetic auth/deadline objects just to load
submission records for complementaria assembly. The command reads the persisted
submission record directly and keeps preflight-shaped synthetic objects out of
the CLI path.

The registry CLI metric output now routes through the shared CLI i18n helper.
Stale CLI tests that expected Modelo 130 registry-backed build/import paths to
fail were rewritten as current-behaviour tests. The broader Modelo 303 user tape
now asserts that unsupported Modelo 303 calculation fails closed until that
modelo has its own registry wave.

## Tests

- `uv run ruff check src/aeat/application/verification src/aeat/entrypoints/cli/filing src/aeat/entrypoints/cli/registry.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run ty check src/aeat/application/verification src/aeat/entrypoints/cli/filing src/aeat/entrypoints/cli/registry.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run pytest src/aeat/application/verification src/aeat/application/filing -q`
- `uv run pytest src/aeat/entrypoints/cli -q`

All passed. The application filing suite still reports four pre-existing skipped
reconciliation tests; this step did not add skips.
