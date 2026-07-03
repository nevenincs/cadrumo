---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S28'
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
     The S28 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Test the plugin materialiser emits a schema-shaped plugin tree from the authored source with the persona and version correctly interpolated and ## Scope

- `src/aeat/agent/tests/test_plugin_workspace.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Test the plugin materialiser emits a schema-shaped plugin tree from the authored source with the persona and version correctly interpolated

## Scope

- `src/aeat/agent/tests/test_plugin_workspace.py`

## Description

- Add `test_plugin_workspace.py` with 10 tests covering the plugin materialiser end to end: manifest shape, skills tree, agents tree with Claude-native frontmatter, `.mcp.json` server declaration, and persona/version interpolation.
- Include a live invocation of `claude plugin validate --strict` against the real emitted tree, asserting exit code 0.
- Commit `80f0043f14`.

## Outcome

- 10/10 tests passed, including the live `claude plugin validate --strict` run.

## Notes

`claude plugin validate --strict` (claude 2.1.199) deep-validates only the manifest, not agent `.md` frontmatter — the never-`mode:` discipline is enforced by this test module's own assertions, not by the validator. No incidents. No skipped work.
