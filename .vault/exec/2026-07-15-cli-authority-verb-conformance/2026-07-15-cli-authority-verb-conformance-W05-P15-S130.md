---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:94e9f49cbb12dfe128e03a6a99f512884e20b3745d2d2a544c63025ba1ae00c3'
step_id: 'S130'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove modelo audit replay result schema and public command key

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py`

## Description

- Confirm the named payload module declares no audit replay result schema.
- Confirm the public replay command key is absent from the live registry.

## Outcome

The named surface carries no replay result schema, and `modelo.audit.replay` is absent from the live registry. The surviving audit keys are `modelo.audit.check`, `modelo.audit.show`, and `modelo.audit.export`, so the replay door was removed rather than renamed or aliased.

The absence is now gated: the retired-key gate landed under S137 covers `modelo.audit.replay`.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
