---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:45024caab76283a0043120ebb6eeda38a4553f58dfdf75b90b250ed65741b293'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `invocation policy review`

## Scope

Reviewed the global TUI request, typed refusal, command-graph posture, root and group
handling, password boundary, locale coverage, and focused real CLI tests against the
accepted TUI and password decisions.

## Findings

### terminal-path-refusal | high | Bare root and executable groups ignored TUI requests

The first implementation enforced refusal only in leaf wrappers, allowing terminal root,
`app`, and `config` invocations to emit ordinary CLI output. Resolved by applying the same
policy at each terminal callback and adding real invocation coverage.

### capability-authority | medium | TUI routing lacked a closed command posture

The first implementation used only a root-context boolean. Resolved by adding the closed
`TuiCapability` axis to the canonical `CommandSpec` authority and routing enforcement
through the shared TUI policy module.

## Recommendations

Keep every future TUI route enrollment on `CommandSpec.tui_capability`, implement its
launcher route before changing the posture to available, and retain root/group/leaf
fixed-point tests so no explicit request can fall back silently.
