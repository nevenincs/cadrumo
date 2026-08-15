---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:e23c6f42ee2051ce97bf8f7256838fd300edaeb6a58aa2c13fcbb7004a4c705a'
step_id: 'S95'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh make the receipt deletion honour the clear outcome it already computes, since the discard helper returns whether the compare-and-clear succeeded and the resume path branches on it, while the revocation entry point calls the same helper bare and returns nothing, so a refused clear is silent and a login can report the prior profile as closed while its acceleration receipt survives on disk, the reachability being narrow because the bytes must change under a held per-profile lock but the reporting value already existing

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_acceleration_receipt.py`

## Description

- Establish reachability by probe rather than by inheriting the row's assumption.
- Raise a typed refusal when the compare-and-clear reports failure, rather than
  propagating a boolean to a caller that ignores it.
- Keep the new error outside the exception type this module already catches and
  logs, so the refusal cannot be swallowed by the existing handler.
- Cover the refusal AND its control, and bite-prove both from outside the repo.

## Outcome

The defect is real and is now a refusal. The compare-and-clear already computes
whether the exact anchored bytes were removed and the resume path branches on
that value; the revocation entry point called the same helper bare and returned
nothing, so a login could report the prior profile closed while its acceleration
receipt was still on disk.

Two of the row's own claims were corrected by the work, in opposite directions,
and both corrections matter more than the fix.

The row asserted the reachability was narrow -- that the bytes had to change
under a held per-profile lock, which is a race. That was inherited, not
measured. With an OPEN HANDLE on the receipt the refusal reproduces
deterministically on Windows, with no race at all: another process reading the
file, a backup agent, an antivirus scanner. So the condition is broader and
simpler than the row believed.

The severity, however, is SMALLER than the row asserted, and this surfaced only
while writing the test. The keychain secret is deleted BEFORE the clear is
attempted. A refusal therefore leaves an orphaned receipt whose key is already
revoked, not a resumable session. The caller is still told the profile is closed
while an artefact remains, which is the campaign's standing defect shape and
worth the fix; but it is not a live resumable login, and the test now asserts the
ordering so that bound stays true. The row should be read as corrected on this
point.

The remedy is a typed error rather than a returned boolean, for a specific
reason: the caller that would ignore a boolean is precisely the caller that
reports the profile closed, so a bool repeats the defect one level up. The new
error deliberately does not subclass the custody record error, because that is
the exact type this module already catches and logs -- subclassing would have
re-swallowed it in the same handler and produced a fix that changed nothing.

Coverage is the refusal and its control together. The control matters: without
an assertion that an unobstructed revocation still removes the receipt, the
refusal test would be satisfied by a function that raises unconditionally and
breaks every logout. The bite proof runs from outside the repo and reds on
DID NOT RAISE, so it tests the behaviour rather than a precondition.

## Notes

The commit's pathspec named the four locale catalogues because the new error
needs a message key in each. Two of them could not be rewritten at commit time
because another writer held the files open, so they went in carrying a
concurrent, unrelated change and left the four catalogues holding different key
sets -- breaking the parity gate at HEAD. That was corrected in a following
commit at blob level, returning the peer's work untouched to their working tree.

The same pathspec had a second, quieter consequence that no signal announced. It
also committed the production module from a working tree that already carried
ANOTHER agent's in-flight relocation imports, so HEAD acquired an import of a
core module that does not exist at HEAD and an import of a name the custody
facade does not yet export. The module cannot import from a clean checkout. The
locale half had a visible cause to point at -- a permission failure printed in
the output -- while the production half had none: no error, and a stat line
reading exactly one file changed, which is exactly what was intended. The count
was right and the content was not.

The durable lesson is narrower than "watch for a failed swap". A pathspec names
a PATH, never a VERSION, and on this tree the version is frequently someone
else's. The check that would have caught it is reading `git diff HEAD` for the
named paths immediately before committing, looking for lines the author did not
write. The repair belongs to the relocation step that owns those files, and was
routed there rather than fixed by a second writer on the same path.

One unrelated failure was attributed structurally and left standing: a keychain
error test asserts English operator text with no language override anywhere in
its conftest chain, while the default output language at HEAD is Spanish. It
cannot pass on this tree in any state and is owned by whoever flipped the
default.
