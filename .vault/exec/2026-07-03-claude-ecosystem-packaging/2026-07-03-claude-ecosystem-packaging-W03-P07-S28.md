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
