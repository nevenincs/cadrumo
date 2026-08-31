---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:7f3818d7afdb93b1615021695135af1db41ad133da3cc01ccd1e530e0efe92a9'
step_id: 'S62'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Check this campaign's verb renames against the profile-bound write guard and bootstrap exemption governed by the cli-authority-verb-conformance ADR, which records a rename silently dropping six verbs out of that guard

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `verify:` `pytest test_bootstrap_exempt_entries_resolve.py test_login_gated_verbs_never_exempt.py application/tests/test_storage_write_policy.py` -> `7 passed unit, 61 passed integration`

## Notes

No code changed. This closes a risk that had been carried unexamined for the
whole campaign, and it was reached only by semantic search over the vault --
the governing record, `2026-07-28-cli-authority-verb-conformance-adr`, had not
been read by this campaign at all.

That ADR documents precisely the failure this campaign was positioned to cause.
The profile-bound write guard was once a hand-maintained catalogue of command
path prefixes, and **a verb rename left six entries naming paths the CLI no
longer exposed, so every invoice mutation fell out of the guard and became
unrefusable under any storage route.** Nothing was visible to any gate. This
campaign renamed or rehomed roughly forty leaves, including one the ADR names
directly: `maintenance reconcile`, which it lists among twenty-five leaves
traced to a bucket-scoped write and guarded, and which this campaign moved to
`config profile archive reconcile`.

The risk did not materialise, and the reason is structural rather than lucky.
The guard is no longer path-keyed: `storage_write_policy.py` derives
`profile_bound_write` from the spec's `write_route`, and states so -- "the
caller obtains the value from validated, CommandSpec-owned policy rather than
reconstructing a command path". A token rename cannot drop a verb out of a
guard that never reads the token. The ADR's amendment records that reshaping.

The surviving path-keyed data is in `_bootstrap_exempt.py`, whose entries carry
`cites_verbs` that must resolve against the live tree. None of them names a verb
this campaign touched, and the resolution gate is green. The one path-keyed
entry this campaign DID invalidate -- the `config storage` exempt subtree, which
still declared `show` -- was caught and fixed under S43 by that same gate.

Sixty-eight tests across both lanes confirm the guard and the exemption are
intact.

One caveat on the discovery itself: the code index answered every query from a
single file and reported 479 missing sections, warning in its own output that an
absent result is not evidence of absence. A rebuild was started. Searches run
before it completes should not be trusted for negative results.
