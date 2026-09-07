---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:f7251fcbaee354594f60a26f98c93e39fd19f4f3ef293f724535918b85c0d5e2'
step_id: 'S102'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Establish that no deletable residue remains, every open decision now being should-be-live or staged rather than superseded, then sharpen the committed-custody entry with the sibling contrast that makes its consequence concrete: the CAS envelope replace directly below the unreached data-file replace carries two consumers because passphrase rotation performs it, same module and same design, so no product operation replaces a committed custody data file and a record needing correction has no guarded path to it.

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/capsule.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/custody/capsule.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `pytest .../storage/tests/ -k "capsule or custody"` 12 passed
- `verify:` the four ledger gates 27 passed; `docstring_reference_ratchet`,
  module ratchet and secure-store gate exit 0
- `verify:` duplication 10 / 0.05%; dead code 0; unused 1031, exact 401
- `verify:` `ruff check` and `ty check` clean

## Notes

A structural fact worth recording before the annotation: NO open cluster is
classed `superseded` any more. The forty-one remaining decisions are thirty-three
`should-be-live` and eight `staged-capability`. Every finding this campaign could
resolve by deleting displaced code has been deleted, and what is left needs a
capability decision or a wiring change rather than a judgement call. That is why
recent steps have been making the code honest rather than shrinking the count:
the count is not the thing left to move.

The custody entry is sharpened rather than reclassified, and the sharpening is a
sibling comparison. `replace_committed_profile_custody_envelope` sits directly
below the unreached `replace_committed_profile_custody_data_file`, carries two
production consumers because passphrase rotation performs it, and shares the CAS
design exactly. Same module, same guard, one wired and one not.

So no product operation replaces a committed custody DATA file, and a record
needing correction has no guarded path to it -- the guard being precisely the
unreached function, which refuses unless the capsule is recognized and the digest
matches. That connects to the repair-remediation decision this ledger records
separately, and it stays open with it.

Both docstrings now name the reached sibling. Naming what IS wired beside what is
not is the form these annotations should take: a reader who can see the contrast
does not have to take the claim on trust.
