---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S153'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Derive exact nested passphrase, recovery, auth, reset, ledger, and audit inputs from accepted schemas

## Scope

- `src/cadrumo/entrypoints/mcp/_input_schema.py`

## Description

- Read the MCP input-schema module and establish whether the per-verb inputs are derived or enumerated.

## Outcome

The inputs are derived rather than hand-listed, which makes the named command groups correct by construction. The module walks the real Typer and Click command tree, reads each command's declared positional arguments and options, and projects them into a strict typed per-verb schema carrying parameter order, JSON type, requiredness, enum choices, multiplicity, and flag shape.

The nested handling the row calls for is the load-bearing part: the module records the resolved path tokens as Click knows them, so an underscored registry key maps onto the hyphenated live command and the built argv actually dispatches. A hand-enumerated schema for the passphrase, recovery, auth, reset, ledger, and audit groups would have drifted; a derived one cannot.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
