---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:2889a7a3b913d14cf631311fcd5ba7fd080179d03f5ccd973ae051a39500e575'
step_id: 'S151'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Reject removed command strings in diagnostics, help, errors, and schema metadata

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_self_referential_string_conformance.py`

## Description

- Run the self-referential string gate and confirm removed command strings are rejected across diagnostics, help, errors, and schema metadata.

## Outcome

The named gate passes and rejects the retired grammar across the diagnostic, help, error, and schema-metadata surfaces. Together with the suggestion gate it closes the loop from both directions: one proves every cited command resolves, the other proves no retired command string survives to be cited.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
