---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S133'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Update the authoritative command manifest to the accepted paths and remove legacy keys

## Scope

- `src/cadrumo/application/operator_surface/_manifest.py`

## Description

- Read the authoritative manifest module and establish how it sources its command keys.

## Outcome

The manifest holds no hardcoded command keys to migrate or remove. It projects the CLI's own registered result-schema registry, which the CLI adapter enumerates and injects, so the manifest cannot carry a legacy key that the registry does not carry.

This is a stronger end state than the Step anticipated: a hand-maintained key list can drift from the live surface, while a derived projection cannot. The retired keys are absent from the manifest because they are absent from the registry.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
