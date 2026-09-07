---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:b1a5dba416ad03275cdc8389b079c9f88805a05684ab9d4d929c09c3baf57dda'
step_id: 'S85'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Wire the bucket output-language hint, which production read and nothing wrote: the hint answers the one question the encrypted preference cannot, which language to speak before the profile is unlocked, and the resolver falls back to it whenever no session is bound, so a language the operator chose during setup silently reverted to the settings default on every pre-login surface. Extend the custody port from read-only to read, write and clear, and mirror the preference from the sole fact-write door, which already special-cases the same path to invalidate the locale cache.

## Scope

- `src/cadrumo/application/user_profile/custody_ports.py`
- `src/cadrumo/adapters/persistence/storage/profile_custody.py`
- `src/cadrumo/application/user_profile/language_resolver.py`
- `src/cadrumo/application/user_profile/fact_write.py`
- `src/cadrumo/application/user_profile/tests/test_language_resolver.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/application/user_profile/custody_ports.py`
- `M` `src/cadrumo/adapters/persistence/storage/profile_custody.py`
- `M` `src/cadrumo/application/user_profile/language_resolver.py`
- `M` `src/cadrumo/application/user_profile/fact_write.py`
- `M` `src/cadrumo/application/user_profile/tests/test_language_resolver.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` unused 1040 -> 1038, exact 411 -> 409; both hint symbols reached
- `verify:` removing the one mirror call fails the new case `None == 'ca'`;
  restored and re-verified
- `verify:` `pytest .../test_language_resolver.py .../test_fact_write_door_contract.py`
  10 passed
- `verify:` module ratchet exit 0; `ruff check` and `ty check` clean
- `verify:` open symbol decisions 55 -> 53

## Notes

A read-never-written store again, and again the reader was the honest half. The
hint exists to answer what the encrypted preference cannot: which language to
speak BEFORE the profile is unlocked.
`resolve_active_profile_output_language` falls back to it whenever no bucket
session is bound, and the reader fails soft on absence -- so while nothing wrote
it the fallback always returned `None`, and a language the operator deliberately
chose during setup reverted to the settings default on every pre-login surface,
with nothing above DEBUG saying so.

The custody port carried only the read. Adding the write and the clear beside it
is a symmetric completion rather than a new boundary: the port already owned
this exact artefact.

The mirror sits at `apply_profile_fact_changes` because that is the sole door
through which the preference can change, and it already special-cased the same
path to clear the locale cache -- so the mirror sits beside the invalidation it
belongs with rather than in a second place that could drift.

Clearing the preference clears the hint, which is what stops the two disagreeing
about an absence, and is why both the writer and the clear were in the cluster.
The mirror swallows failure for the same reason the read does: it carries a
convenience, and a hint that could not be written must not fail the fact write
that owns the real value.

This is the shape the secure-store gate was built for, and that gate could not
see it: a file-backed hint is not a `SecureBoundRepository`, so the write-path
scan does not reach it.
