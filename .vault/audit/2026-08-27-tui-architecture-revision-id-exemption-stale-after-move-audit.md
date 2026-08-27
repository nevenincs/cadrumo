---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:748fa489841a3f629e2f46951de33345b931a24739d15511570156aac48499a9'
related: []
---

# `tui-architecture` audit: a stale exemption path, not a resolution defect

## The red gate

`test_every_production_select_revision_call_is_law_determined` fails:

    new production site(s) pass revision_id into select_revision resolution;
    prove they only assert-equal against the law-determined pick (never inject)
    and, if so, enroll them in _SANCTIONED_REVISION_ID_SITES:
    ['domain/calculations/registry/_snapshot_internals.py']

This guards the rule that matters most for cross-year correctness: a stored
`revision_id` may only be asserted equal to the law-determined resolution, never
injected as the selector, because injection is "the defect class that lets one
year's numbers be computed under another year's norms".

## It is not that

The call moved; it did not change shape.

- `registry/snapshot.py` — the enrolled path — now contains **zero**
  `select_revision(...)` calls passing `revision_id`.
- `registry/_snapshot_internals.py` contains exactly **one**, in
  `_build_validated_snapshot` (line 223).
- Both modules exist, so this is a split, not a rename.

And the shape is the sanctioned one. `select_revision` reaches
`_revision_matches_request`, which uses the argument only as an equality filter:

    if revision_id is not None and revision.id != revision_id:
        return False

That is a narrowing, and `aeat-registry-authority-flow` states the consequence
directly: "The non-overlap window gate guarantees resolution is unique, so a
narrowing can only equal the law-determined pick or refuse." It cannot select a
different revision.

## Why the gate still deserves to be red

The exemption is keyed by module path, so a peer's module split silently
invalidated it. That is the failure mode `aeat-quality-gates` warns about when it
says allowlists are "where the judgement moves" and that stale entries must fail.
The gate did exactly its job: it noticed that the attestation no longer covers the
code it was written for.

## Remedy, for the module's owner

Enrolling `domain/calculations/registry/_snapshot_internals.py` in
`_SANCTIONED_REVISION_ID_SITES`, and dropping `snapshot.py` if it no longer
qualifies, restores the gate. That is deliberately left to whoever owns the split:
enrollment is an attestation that the site only assert-equals, and the person who
moved the code is the one who can make it.

## The other four reds in the same sweep

A full run of the registry test directory after reverting my own work
(`8258892c64`) leaves these, none of them mine:

- `test_registry_schema_part1.py` — two Modelo 200 envelope/grupo-mercantil
  validator expectations.
- `test_registry_reviewability.py` — the validator-complexity ratchet exceeded.
- `test_record_design_source_selection.py` — a record-design import boundary.

Recorded so the next sweep does not re-derive their attribution.
