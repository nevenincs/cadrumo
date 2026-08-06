---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:1c717b5a36d8f3dff788bada45b1d4c264529832709095685e9a358a53ea5fa9'
step_id: 'S154'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove legacy MCP tool keys and dispatch only accepted CLI mirrors

## Scope

- `src/cadrumo/entrypoints/mcp/_tools.py`

## Description

- Read the MCP tool builder and establish where its keys come from.
- Sweep for legacy tool keys.

## Outcome

The tool descriptors are built from the live capability manifest joined to the registered result schemas, so the exposed keys are a projection of the live surface rather than a maintained list. A legacy key cannot survive here, because it would first have to survive in the manifest and the registry, and the preceding Phase confirmed the retired keys are absent from both. A direct sweep for the retired tool keys finds none.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
