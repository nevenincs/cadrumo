---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `domain-portals-harvest`

## Findings

The portals domain already provides local registry discovery APIs:
`PORTAL_REGISTRY`, `get_portal`, `portals_for_modelo`, and
`portals_by_category` in `src/aeat/domain/portals/_registry.py`.

The existing `src/aeat/domain/portals/_cli.py` is the wrong surface for the
redesigned CLI. It is a domain-local `aeat portals` app, uses `--json`, renders
Rich tables, and emits through `emit_json_success` rather than the root
`--format` option and `_emit`.

Target placement is `aeat app live portals ...`, matching the accepted
`app-live-shape` ADR. The commands are local discovery only unless a future
explicit `--check-live` mode is designed and guarded by `require_live_read()`.

Suggested command shape:

```text
aeat app live portals list [--category CATEGORY] [--modelo MODELO] [--active-only] [--format json|text]
aeat app live portals show PORTAL [--format json|text]
```

Reject `aeat portals ...` because it violates the root contract and risks
keeping the old domain-local CLI as a shim. Reject `aeat app registry
portals ...` because accepted app-live design places portal discovery with the
live-facing surface. Reject `open`, `submit`, `present`, `sign`, `pay`, and
navigation verbs. Payment portals may be listed as metadata only; no action
verbs are accepted.

Both commands emit typed payloads via `_emit` and emit no bucket event.
