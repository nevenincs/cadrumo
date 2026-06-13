---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W04.P13.S46'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# W04.P13.S46 - Resolve CLI doc-reference payload import candidates

Scope: Close the Vulture candidates for
`src/aeat/entrypoints/cli/_doc_reference.py` without replacing the lazy CLI
schema-registration mechanism.

## Description

- Keep the CLI payload imports as explicit schema-registration side effects.
- Bind those imported modules into a `payload_schema_modules` tuple and verify
  each module exposes `__name__`, making the side-effect registration visible to
  dead-code analysis.
- Verify that Vulture reports no remaining production dead-code candidates.

## Outcome

The CLI reference generator still imports every payload module before inspecting
`SCHEMA_REGISTRY`, and Vulture now sees the imported modules as intentionally
used. W04.P13's dead-code candidate list is closed.

## Notes

The worktree already contained broader CLI doc-reference edits around language
pinning and write-if-changed behavior. This step commits only the payload-module
registration visibility change plus Vault tracking, leaving that broader WIP
uncommitted. The docs conformance tests pass, but the committed-reference drift
test still fails because `app.live.filed.capture-all` is live and `docs/cli` has
not been regenerated.
