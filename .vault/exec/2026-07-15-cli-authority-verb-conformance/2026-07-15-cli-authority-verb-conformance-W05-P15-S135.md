---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:0b44985de4b4ba48d94a40c412e3efb636b7f63aa661b421be90c32eaa014d40'
step_id: 'S135'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Replace the rekey recovery diagnostic with config passphrase change

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`

## Description

- Read the recovery diagnostics emitted by the named master-key module and confirm the retired rekey verb is no longer cited.

## Outcome

The named surface cites the accepted `aeat config passphrase change` verb in its custody diagnostics, and the retired rekey verb appears nowhere in the module. One diagnostic pairs the passphrase-change verb with `aeat config recover`, which is the correct accepted pair for a custody change against a recovery path.

The citation is under CI enforcement rather than resting on this reading: the suggestion-conformance gate resolves every production string literal in this package against the live command tree, so a dead verb here would fail that gate.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
