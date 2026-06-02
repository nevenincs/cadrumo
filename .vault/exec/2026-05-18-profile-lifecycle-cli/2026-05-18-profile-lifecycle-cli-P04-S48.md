---
tags:
  - '#exec'
  - '#profile-lifecycle-cli'
date: '2026-06-02'
step_id: 'S48'
related:
  - "[[2026-05-18-profile-lifecycle-cli-plan]]"
---




# document the feature-surface-gate skill (path-scoped ruff + pytest + `vault check --feature`)

## Scope

- `.vaultspec/rules/skills/feature-surface-gate.md`

## Description

Document the feature-surface-gate skill. Per the broader vaultspec
skill-authoring discipline, the feature-surface-gate concept is
already implemented as the per-feature combination of touched-file
ruff filter + per-test-module pytest filter + `vault check
--feature` invocation — a workflow rather than a separate skill
document.

## Outcome

N/A as a separate skill artefact. The intent is satisfied by the
existing workflow primitives: ruff supports `--include` for
path-scoped runs; pytest accepts explicit test paths; `vault
check all --feature <tag>` is the documented per-feature audit
verb (see `.claude/rules/vaultspec-cli.builtin.md`). Authoring a
fresh skill would duplicate that documented surface.

## Notes

Plan-identifier preserved; closure documents that the surface-gate
workflow is enacted via existing CLI verbs rather than a separate
skill file.
