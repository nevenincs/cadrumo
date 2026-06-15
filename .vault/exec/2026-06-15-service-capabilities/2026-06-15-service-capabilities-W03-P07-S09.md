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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace service-capabilities with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-06-15-service-capabilities-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Capability extras + relocate torch and ## Scope

- `just doctor/provision recipes`
- `fix env-playwright`
- `reconcile README/justfile`
- `pyproject.toml`
- `justfile`
- `README.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

## Outcome

S09 is complete. A bare `pip install aeat` is now lean — the optional Google / browser / Anthropic stacks install only on demand — while the dev environment stays identical. The doctor reconciles each enabled capability against its extra's availability and prints the exact install command, giving the cohesive graceful-degradation behaviour the campaign set out to deliver. deptry clean, import contracts 4 kept / 0 broken, json-schema conformance + provisioning/doctor suites green.

## Notes

The feature-boundary inline guards (converting a raw deep `ModuleNotFoundError` at the exact moment a feature with a missing extra is invoked, rather than at the doctor) were intentionally not added: they would require making the browser / google / anthropic adapters' eager top-level imports lazy and risk a layer-direction violation. The doctor's reporting + `require_optional_extra` helper provide the actionable guidance; the deep raw error only appears if a feature is invoked without first running `aeat config check`.
