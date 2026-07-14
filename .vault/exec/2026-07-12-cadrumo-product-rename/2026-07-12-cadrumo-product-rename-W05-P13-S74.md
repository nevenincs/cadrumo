---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S74'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---




# Regenerate API references and documentation indexes from CADRUMO source authorities

## Scope

- `generated documentation surfaces`

## Description

- Confirmed the generated API-stub tree already reflects the `cadrumo` source authority: commit `44776fed46` (`W05.P13.S72, S74`) retargeted `dev/docs/apidocs`, `dev/docs/build.py`, `dev/docs/cli_reference.py`, and the terminology/preprocess generator modules to the current product identity ahead of this record.
- Ran `uv run --no-sync python -m dev.docs.apidocs scaffold --check` against the current tree.

## Outcome

`scaffold --check` reports "Stub tree is conformant. No drift detected." — zero missing, orphaned, or stale `docs/api/*.rst` stubs against `src/cadrumo`. The generated-reference regeneration this Step names is verified green with no further mutation required.

## Notes

This Step's scope is the mechanical generator surface only (`dev.docs.apidocs`). It does not carry the full documentation-authoring lifecycle that gates the sibling content Steps in this phase (`S68`-`S71`, `S73`), whose independent reviews are failing on a missing Phase 3/Phase 8 user-approval record rather than on content. That blocker is out of this Step's scope and has been escalated separately.
