---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S38'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace claude-ecosystem-packaging with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S38 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Test the generator emits a schema-shaped marketplace tree whose plugins[] entry resolves to the emitted plugin and ## Scope

- `src/aeat/agent/tests/test_marketplace_generation.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Test the generator emits a schema-shaped marketplace tree whose plugins[] entry resolves to the emitted plugin

## Scope

- `src/aeat/agent/tests/test_marketplace_generation.py`

## Description

- Add `test_marketplace_generation.py`: the emitted manifest is schema-shaped and its `plugins[]` source resolves to the plugin materialised in the same call; the served plugin is byte-identical to a standalone `materialise_plugin` emission (no drift by construction); the checked-in `packaging/marketplace` scaffold equals the generator output (scaffold-lock); and where the `claude` CLI is on PATH the emitted marketplace passes `claude plugin validate --strict` as an additional gate (structural assertions always run).
- Commit `4da3a62c05`. 4 passed; ruff clean.

## Outcome

- Marketplace/plugin/scaffold coherence is gate-enforced, including against the live validator.

## Notes

Authored inline by the coordinator (the original executor died at the rate limit before starting this step). Includes one beyond-plan assertion — the scaffold-lock test — so a hand-edit to `packaging/marketplace/.claude-plugin/marketplace.json` that diverges from the generator fails CI.
