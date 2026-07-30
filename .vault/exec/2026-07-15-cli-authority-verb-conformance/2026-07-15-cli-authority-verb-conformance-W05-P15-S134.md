---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S134'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Update nested command-path token handling and examples for passphrase, recovery, auth, and reset groups

## Scope

- `src/cadrumo/entrypoints/cli/_errors.py`

## Description

- Read the command-identifier mapper in the named module.
- Probe it with the passphrase, recovery, auth, and reset group paths and compare each result against the live registry keys.

## Outcome

The mapper handles nested command paths generically rather than by enumerating groups: it drops the root program token, joins the remaining tokens with dots, and maps hyphens to underscores per token, which is the exact inverse of the CLI token convention.

A probe confirms every named group resolves to its real registered key, including `aeat config passphrase change` to `config.passphrase.change`, `aeat config recovery verify` to `config.recovery.verify`, `aeat config auth reset` to `config.auth.reset`, and `aeat config reset start` to `config.reset.start`. Because the handling is generic, the four named groups are correct by construction and a future nested group needs no further change here.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
