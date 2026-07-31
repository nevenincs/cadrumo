---
tags:
  - '#exec'
  - '#distribution-harness-identity'
date: '2026-07-18'
modified: '2026-07-19'
body_hash: 'sha256:63eb059b19132ec4988d9776bda8a10b8544c99408402de04e1126b273ac2f96'
step_id: 'S01'
related:
  - "[[2026-07-18-distribution-harness-identity-plan]]"
---

# Rename the seven operator rule documents to the cadrumo- prefix and sweep every consumer in one atomic hard-cut commit: generated CLAUDE.md rule imports, MCP rule resources, operator_rules_text callers, the test_operator_rules_exist assertion, and the rule generation tests

## Scope

- `src/cadrumo/_data/agent/rules/`

## Description

- Renamed the seven authored operator rule documents under `src/cadrumo/_data/agent/rules/` to the `cadrumo-` prefix with `git mv` (`operator-envelope-reading`, `operator-grounding`, `operator-honest-declaration`, `operator-lifecycle-ordering`, `operator-operating-rules`, `operator-orientation-routing`, `operator-safety-handoff` -> `cadrumo-operator-*`).
- Updated the harness data-ships assertion set (`test_harness_data_ships.py`) to the seven prefixed filenames.
- Updated the `test_operator_rules_exist` assertion in `test_rule_surface_conformance.py` and the workspace/plugin generation assertions (`test_workspace.py`, `test_app_agent_workspace.py`, `test_app_agent_plugin.py`) that pin `cadrumo-operator-operating-rules.md`.
- Swept the eval-runner and eval-model prose and the lifecycle-contradiction golden docstring citations of `operator-lifecycle-ordering` (name and repo path) to the prefixed identifier.
- Swept the sixteen skill prose cross-references (`SKILL.md` and `reference/casillas.md`) that cite `operator-grounding`, `operator-safety-handoff`, and `operator-orientation-routing` in backticked "see ..." pointers.

## Outcome

- The generator, MCP resources, and MCP prompt-resource projections auto-derive rule identity from the filename, so no generator code change was needed; the renames flow through automatically.
- Green gates: `pytest --collect-only -q src/cadrumo` clean (12967 collected); `src/cadrumo/agent/tests` + lifecycle golden 39 passed; `src/cadrumo/entrypoints/mcp/tests` + the two CLI agent tests 274 passed; ruff check + format clean on all eight touched Python files; ty clean on the two modified non-test modules.
- The distribution-identity verifier self-test under `dev/packaging/tests` stays red by design (re-baselined in P04.S10); it was not touched.

## Notes

- No incidents. The skill prose edits touch rule-citation lines only, disjoint from the skill directory renames and `name:` frontmatter that S03 will move.
