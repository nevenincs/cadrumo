---
tags:
  - '#exec'
  - '#distribution-harness-identity'
date: '2026-07-18'
modified: '2026-07-19'
step_id: 'S03'
related:
  - "[[2026-07-18-distribution-harness-identity-plan]]"
---

# Rename the 34 skill directories and their SKILL.md name frontmatter to the cadrumo- prefix and sweep intra-skill name cross-references, the eval scenario skill_name fields, and the skill-name generation tests in one atomic commit

## Scope

- `src/cadrumo/_data/agent/skills/`

## Description

- Renamed all 34 skill directories under `src/cadrumo/_data/agent/skills/` to the `cadrumo-` prefix with `git mv`.
- Lifted each `SKILL.md` `name:` frontmatter field to `cadrumo-<skill>` so it matches its renamed directory (enforced by `test_skill_applies_when`).
- Swept every intra-skill backtick cross-reference (handoff/itinerary prose in `SKILL.md` and `reference/*.md` citing sibling skills) to the prefixed identifier.
- Updated the eval scenario `skill_name` fields in all ten `scenarios/*.toml` (validated against shipped skills by `run_golden_scenario`) plus the backtick skill citations in their comment prose.
- Updated the skill-name assertions in the generation and delivery tests: `test_workspace.py`, `test_plugin_workspace.py`, `test_app_agent_plugin.py`, `test_app_agent_workspace.py` (materialised `cadrumo-preparar-modelo-130` skill tree), `test_harness_delivery.py` (SKILL resource-URI leaf + `name:` frontmatter assertion), and `test_prompts.py` (prompt name + skill_texts key).

## Outcome

- The plugin/workspace/marketplace generators, the MCP skill resources, and the skill-derived prompt catalogue all auto-derive skill identity from the directory name (`_shipped_skill_names()`, `iter_skill_documents()`), so no generator source change was needed; the renames flow through automatically.
- Green gates: `pytest --collect-only -q src/cadrumo` clean (12975 collected); the combined agent + eval + MCP + CLI-agent run was 400 passed (the two earlier marketplace-bilingual failures cleared once peer P03 S08 committed). ruff check + format clean on the six touched Python test files.
- The untracked `packaging/marketplace/plugins/cadrumo/skills/` scaffold is a locally-regenerated artifact (not git-tracked) and is not part of this commit; no test reads it. The distribution-identity verifier self-test stays red by design until P04.S10.

## Notes

- No incidents. `packaging/mcpb/manifest.json` carries live peer P03 (S09) MCPB-bilingual WIP; S03 does not touch it and it is excluded from this commit. `test_plugin_workspace.py` (whose persona assertions were carried into peer commit `8453908726`) shows only my four skill-line edits here, disjoint from the committed peer content.
