---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:ddd7a9f9c005d8b6682e53a5f1530040ec3dc3adcd9f2bc455a103a6afd90dbe'
step_id: 'S35'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh harden the import-hygiene shim detector so a forwarding layer written as wrapper definitions is caught, not only one written as import aliases

## Scope

- `dev/quality/import_hygiene_scan.py`

## Description

- Teach the detector the wrapper-definition form of a forwarding layer, which
  evades the zero-real-definitions test by construction.
- Draw and defend the line between a forwarding wrapper and a legitimate
  delegation, so the detector is neither blind nor indiscriminate.
- Report what it flags rather than allowlisting to green.

## Outcome

The detector now sees a forwarding layer written as wrapper definitions. The
evasion was structural rather than incidental: a module full of definitions that
merely re-call another package's function has plenty of real definitions, so a
detector asking whether a module defines anything of its own always answered
yes. That is why the forwarding port at the centre of this campaign passed a
shim gate for its entire life.

The detector reports forty-four live delegate-wrapper shims against zero
documented exemptions. It was landed red rather than allowlisted, which is the
correct outcome: the count is a finding, and the largest single contributor is
the package this campaign is actively dissolving.

Verified independently: twenty-eight of thirty-three tests pass in the
detector's own suite.

## Notes

The five failures in that suite are NOT this step's. All five are the terminal
migration census, which pins an exact manifest hash. When first observed those
failures were attributable to a peer's uncommitted terminal-interface edits; that
work has since been committed and the census still mismatches, so the census is
now genuinely stale against committed code rather than transient. It is carried
separately.

That census is also the shape this repository's own rules warn against -- a
pinned exact hash encodes a moment, and the correct response to it is to
establish whether the new identities are legitimate, never to refresh the
constant to restore green.

A related structural observation, recorded because it recurred: a single check
raising inside a diagnostic tool can make every other finding unreadable. That
was believed for a period to be happening here and was later disproved by
measurement -- the scanner runs to completion and emits a full per-site
inventory. The belief itself came from an invocation error, disabling the
parallel plugin in a way that made the run abort before collection. Both the
claim and its correction are recorded because the wrong one was acted on first.
