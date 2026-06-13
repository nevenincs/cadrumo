---
name: 2026-04-13-modelo-inventory-phase-all-summary
description: Phase-all summary for the #108 modelo inventory catalogue feature
type: exec
tags:
  - "#exec"
  - "#modelo-inventory"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-modelo-inventory-plan]]"
  - "[[2026-04-13-modelo-inventory-adr]]"
  - "[[2026-04-13-modelo-inventory-research]]"
  - "[[2026-04-13-modelo-inventory-phase1-scaffold-exec]]"
  - "[[2026-04-13-modelo-inventory-phase2-enums-models-exec]]"
  - "[[2026-04-13-modelo-inventory-phase3-errors-exec]]"
  - "[[2026-04-13-modelo-inventory-phase4-entries-exec]]"
  - "[[2026-04-13-modelo-inventory-phase5-registry-exec]]"
  - "[[2026-04-13-modelo-inventory-phase6-casilla-xref-exec]]"
  - "[[2026-04-13-modelo-inventory-phase7-cli-exec]]"
  - "[[2026-04-13-modelo-inventory-phase8-public-api-exec]]"
  - "[[2026-04-13-modelo-inventory-phase9-green-gates-exec]]"
---

# phase-all summary — modelo inventory (#108)

## phase-by-phase delivery

- **Phase 1 — scaffolding** (`5b9b3e7`). Empty module skeleton for
  `src/aeat/domain/modelos/` and 20 entry stubs, placeholder unit tests.
- **Phase 2 — enums + primitive models** (`1c42e77`). `ModeloCode`,
  `ModeloCategory`, `ModeloCadence`, `TaxpayerProfile`,
  `LegalCitationSource`, `LegalCitation`, `ModeloApplicability`,
  `ModeloMetadata` with partition and trilingual validators.
- **Phase 3 — error hierarchy** (`b2154d3`). `ModeloRegistryError`
  base rooted at `AeatError`; `UnknownModeloError` and
  `RegistryIntegrityError`.
- **Phase 4 — 20 modelo entries** (`3f3817e`). Full research-backed
  metadata for all 20 modelos via a private `_common.py` builder,
  with trilingual display labels, curated Spanish citations, D2
  partition buckets, and known gotchas.
- **Phase 5 — registry assembly + `year_plan`** (`74a6362`). Frozen
  `MODELO_REGISTRY`, import-time `_finalise_registry` invariants,
  `get_modelo` / `modelos_for_profile` / `year_plan` public helpers.
- **Phase 6 — casilla cross-reference** (`bcceb3c`). `pathlib`-based
  walk of `corpus/casillas/modelo_*` asserting every discovered
  modelo resolves in the registry.
- **Phase 7 — CLI subcommands** (`b334637`). Typer `list` / `show` /
  `applicable-to` / `year-plan` wired through
  `src/aeat/entrypoints/cli/modelos/__init__.py` into the root `aeat` app.
  Added a `src/aeat/domain/modelos/_cli.py` per-file B008 ignore in
  `pyproject.toml` matching the existing Typer treatment.
- **Phase 8 — public API lock** (`0e8fbd2`). `src/aeat/domain/modelos/__init__.py`
  docstring + locked `__all__` covering the 15 symbols from the
  plan.
- **Phase 9 — green gates** (`bf9e57b`). All four local gates
  passed against Phase 8 HEAD; the only cleanup was a defensive
  UTF-8 stdout reconfigure in `_cli.py` so the trilingual labels
  render on Windows cp1252 consoles.

## final gate outcomes (tail)

`just lint`
```
uv run ruff check .
All checks passed!
```

`just typecheck`
```
uv run ty check src tests
All checks passed!
```

`just test`
```
tests/test_release_config.py::test_no_release_please_github_actions_workflow PASSED [100%]
=============== 756 passed, 1 skipped, 23 deselected in 30.15s ================
```

`just hooks`
```
uv run prek run --all-files
trim trailing whitespace.................................................Passed
fix end of files.........................................................Passed
check yaml...............................................................Passed
check toml...............................................................Passed
check for added large files..............................................Passed
check for merge conflicts................................................Passed
detect private key.......................................................Passed
ruff (legacy alias)......................................................Passed
ruff format..............................................................Passed
ty type check............................................................Passed
```

## commit history

```
bf9e57b chore(models): lint + typecheck + test green gates (#108)
0e8fbd2 docs(models): public API docstrings + __all__ lock (#108)
b334637 feat(models): CLI subcommands list/show/applicable-to/year-plan (#108)
bcceb3c test(models): cross-reference casilla catalogue coverage (#108)
74a6362 feat(models): assemble MODELO_REGISTRY with import-time integrity invariant (#108)
3f3817e feat(models): populate registry with 20 modelo metadata entries (#108)
b2154d3 feat(models): error hierarchy for registry lookups (#108)
1c42e77 feat(models): add ModeloCode/Category/Cadence/Profile enums + LegalCitation/Applicability/Metadata (#108)
5b9b3e7 feat(models): scaffold aeat.domain.modelos registry module skeleton (#108)
```

## deviations

- **`DeadlineRule` dropped** (ADR §7 vs. reality). ADR §7 referenced
  a `DeadlineRule` type on `aeat.domain.deadlines`; no such type exists on
  `main`. The plan self-review accepted dropping the field and
  resolving deadlines at query time via
  `DeadlineEngine.compute`. Implementation honours the plan.
- **`caps_into` for modelo 123**. Research says `caps_into=193`;
  193 is not in the v1 registry. Stored as `None` with a gotcha,
  per plan.
- **`__all__` tuple order is alphabetical.** Ruff RUF022 auto-sorted
  the locked tuple on first run in Phase 8. The set of exported
  symbols is identical to the ADR §12 tuple; semantics unchanged.
- **`pyproject.toml` B008 ignore extended** to cover
  `src/aeat/domain/modelos/_cli.py`, matching the existing per-file pattern
  for `src/aeat/entrypoints/cli/**`. No new ruff rules added, no `# noqa` or
  `# type: ignore` bandages introduced.

## pointers

- Plan: `.vault/plan/2026-04-13-modelo-inventory-plan.md`
- ADR: `.vault/adr/2026-04-13-modelo-inventory-adr.md`
- Research: `.vault/research/2026-04-13-modelo-inventory-research.md`
