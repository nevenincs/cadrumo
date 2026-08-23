# Rejected mutable-tree operator note

This is an unaudited operator note, not retained execution evidence. The raw
mutable-tree envelopes were deliberately discarded because their source states
were not coherent and they cannot support a performance claim.

The first attempted sweep was terminated and rejected after 48 of 361 live
nodes. It had no frozen source identity, so concurrent shared-worktree edits
allowed different fresh processes to import different source states.

The diagnostic captured `child-exception` / exit-code 1 for all measured
resolution and help samples of these paths:

- `aeat app ledger export`
- `aeat app ledger history`
- `aeat app ledger import`
- `aeat app ledger inventory`

A fresh manual `ledger export --help` profile succeeded immediately afterward.
That disagreement proved the capture was mixing source states, not measuring a
single reproducible application. None of its samples were copied into
`baseline.json` and no failed path was selectively rerun.

The accepted sweep starts from zero and binds every child to one copied source
tree, content digest, originating Git revision, opaque dirty-worktree
fingerprint, and exact live census. The generator refuses resume when any of
those identities no longer match.
