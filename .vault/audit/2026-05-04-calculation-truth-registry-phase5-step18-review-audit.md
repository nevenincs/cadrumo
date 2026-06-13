---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-04-calculation-truth-registry-phase5-step18-exec]]'
---



# `calculation-truth-registry` Code Review


P5S18-001 | MEDIUM | Declaration verification kept a soft missing-registry verdict

`src/aeat/application/verification/_verify.py` returned a `VerificationVerdict`
with `UNVERIFIABLE` when no registry snapshot existed for a parsed declaration.
The accepted registry ADR requires filing-grade workflows to fail hard on
missing, incomplete, contradictory, stale, provisional, or incalculable registry
definitions. Returning a soft verdict could let declaration import appear
successfully classified while no legal calculation authority exists.

## Resolution

- P5S18-001: fixed before commit. Declaration verification now raises
  `VerificationError` when the modelo is absent from the registry or snapshot
  validation fails. `VerificationStatus.UNVERIFIABLE` and the unverifiable
  verdict helper were removed from the verification schema/path. The filing CLI
  converts verification errors into `typer.BadParameter` so the command fails
  closed without traceback-shaped UX.

No additional HIGH or CRITICAL issues were found in the reviewed slice.
Residual risk is limited to the deliberately unsupported Modelo 303 and Modelo
100 registry waves, which now fail closed instead of using removed formula or
verification paths.

Verification passed:

- `uv run ruff check src/aeat/application/verification src/aeat/entrypoints/cli/filing src/aeat/entrypoints/cli/registry.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run ty check src/aeat/application/verification src/aeat/entrypoints/cli/filing src/aeat/entrypoints/cli/registry.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run pytest src/aeat/application/verification src/aeat/application/filing -q`
- `uv run pytest src/aeat/entrypoints/cli -q`
