---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:6b8b9bc6603230c5eececd84267acb211ae8c81120de4933efc43240511f7061'
step_id: 'S100'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Take the top of the hiding-rank list, a port accessor in a module ninety-seven percent live, and settle it with the sibling comparison: its neighbours carry four, three and two production consumers while it carries zero and nothing reaches the port method under it either, which reads as a displaced facade and is not, because the operation is performed by an adapter calling list_keys on the repository it owns. Nothing at the application layer lists namespaces, so this is a port waiting for a consumer rather than one something replaced, and the accessor now says so.

## Scope

- `src/cadrumo/application/user_profile/custody_ports.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/application/user_profile/custody_ports.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `pytest src/cadrumo/application/user_profile/tests/ -k "custody_port or port"`
  124 passed
- `verify:` the four ledger gates 25 passed; `docstring_reference_ratchet`,
  module ratchet and secure-store gate exit 0
- `verify:` duplication 10 / 0.05%; dead code 0; unused 1033, exact 404
- `verify:` `ruff check` and `ty check` clean

## Notes

Top of the hiding-rank list, and the sibling comparison settled it in one
measurement: the record-crypto accessor carries four production consumers,
bucket storage three, the output-language hint two, and this one zero. Nothing
reaches the `secure_object_inventory` port method directly either, so the whole
inventory path through the application boundary is unreached.

That reads as a displaced facade -- the shape the profile-key alias turned out
to be -- and it is not. The operation IS performed:
`adapters/persistence/profile/participation_index.py` calls `list_keys` straight
on its own `SecureObjectRepository`. An adapter using persistence it owns is
allowed and is not a boundary violation, so what the measurement actually shows
is that no APPLICATION module lists namespaces, and this is the port through
which one would.

Staged rather than orphaned or superseded, and the distinction is load-bearing:
a superseded facade should be deleted, a staged port should not, and the same
zero-consumer count supports both readings until you find where the work is
actually done.

The module is ninety-seven percent live, which is exactly why the gap is
invisible from inside it, so the accessor's docstring now states that it is
declared and not yet reached and names the adapter doing the work.
