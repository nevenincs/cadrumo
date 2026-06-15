---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S09'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---




# Capability extras + relocate torch

## Scope

- `just doctor/provision recipes`
- `fix env-playwright`
- `reconcile README/justfile`
- `pyproject.toml`
- `justfile`
- `README.md`

## Description

Provisioning / doctor / recipes (committed earlier):

- Add `just doctor` (runs `aeat config check`) and `just provision` (runs `env-playwright`) recipes; chain `just bootstrap` to end with `-just doctor` (commit `f926b41c8`).
- Fix the broken `env-playwright` recipe to `playwright install chromium` (was a dead `python -m aeat.entrypoints.cli.browser.health` reference) (commit `f926b41c8`).
- Reconcile `README.md` fresh-clone entry point to `just bootstrap` + `just doctor` (commit `5dc9e2a15`).
- Relocate torch out of `[project.dependencies]` to the dev group — split into its own step S13 (commit `93d903f30`).

Lean-core capability-extras migration (completed):

- Move `google-auth` / `google-auth-oauthlib` / `google-api-python-client`, `playwright` / `playwright-stealth`, and `anthropic` out of `[project.dependencies]` into capability-mapped `[project.optional-dependencies]` extras (`google`, `browser`, `anthropic`, plus an `all` aggregate). Pull all six into `[dependency-groups].dev` so the dev/test/CI environment is unchanged for every peer. deptry `aeat` self-reference ignore; drop two `.importlinter` entries orphaned by the bundled `filing.reconciliation` removal (commit `2490c33af`).
- Verified the core CLI builds without any of the optionals loaded (`importlib` `sys.modules` check), so removing them from the runtime deps is safe; `uv lock` resolved 265 packages with zero version changes.
- Graceful degradation: add `OptionalExtra` / `OPTIONAL_EXTRAS` and `probe_optional_extra(s)` (spec-only, never raises) + `require_optional_extra` (instructive ImportError) to `provisioning.py`; `aeat config check` now reports each extra's importability and raises an issue when `google_export` is opted in but the `google` extra is absent (commit `dd6122263`).
- Document `pip install aeat[google|browser|anthropic|all]` in the onboarding guide (commit `975a98e39`).

Feature-boundary guards (completed — no longer a non-goal):

- Add the guard primitive to `core` (innermost layer, importable by every adapter without a layer violation): `OptionalExtra`, `GOOGLE/BROWSER/ANTHROPIC_EXTRA`, `optional_extra_available` (spec-only), and `require_optional_extra` raising the typed `MissingOptionalExtraError` (an `ImportError` subclass carrying `install_hint`).
- Make the eager-import adapters import-safe: anthropic adapter is lazy (`_providers.__getattr__` + imported in `LLMClient._build_adapter` only behind the guard); `_playwright.py` falls back to stub exception classes when playwright is absent; browser `session.py`/`evasion.py` move playwright types to `TYPE_CHECKING` and lazy-import `ProxySettings` at its one use.
- Guard each feature at its own boundary, raising the feature's native typed error: anthropic → `LLMConfigError`, browser `_start_playwright` (the single runtime chokepoint) → `BrowserError`; google's pre-existing `ImportError` guards' hints move to `pip install aeat[google]`.
- Real-behaviour tests via a `sys.meta_path` import blocker (no mocks): the CLI builds with all three extras blocked, and each boundary refuses with its `pip install aeat[<extra>]` hint (commit `3a0ab7823`).

## Outcome

S09 is complete. A bare `pip install aeat` is now lean — the optional Google / browser / Anthropic stacks install only on demand — while the dev environment stays identical. The package imports without any extra installed; reaching a feature whose extra is absent refuses with the feature's own typed error naming the exact install command, and the doctor reconciles each enabled capability against its extra. deptry clean, import contracts 4 kept / 0 broken, ty clean, json-schema + 597 adapter/degradation/import-smoke tests green.

## Notes

The feature-boundary guards were initially deferred (raw `ModuleNotFoundError` at invocation) on a layer-violation concern. That concern was resolved by siting the guard primitive in `core` rather than `application` — `entrypoints > adapters > application > domain > core`, so an adapter importing `core.require_optional_extra` is contract-legal — and by making the eager-import adapter modules import-safe. The deep raw error no longer appears on any path.
