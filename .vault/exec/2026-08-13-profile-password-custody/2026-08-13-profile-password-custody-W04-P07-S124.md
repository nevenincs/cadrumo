---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
step_id: 'S124'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh reconstruct the rotation crash-window coverage against the two surviving stores after the module was deleted whole to unblock collection

## Scope

- `src/cadrumo/adapters/persistence/storage/tests/`

## Description

- Rebuild both booked losses against the two surviving stores.
- Establish honestly whether two stores exercise what three did.
- Bite-prove each test rather than asserting coverage.

## Outcome

Three tests, verified independently at three passed. Both booked losses are
covered: the crash window between envelope and blob-store rotation, and the
probe-skip idempotency that makes re-running a partial rotation a clean no-op.

**The assertions are built against the two ways this coverage could pass
vacuously.** Each test asserts BOTH stores under BOTH keys, because "loads under
the new key" alone is satisfied by a store that never moved. And the blob
payload is compared byte-for-byte after convergence, so a rotation that
re-encrypted *different* bytes fails rather than passing as "it decrypts".

**The interleaving question was answered honestly and against the step's own
interest.** Three stores have two inter-store boundaries; two stores have one.
The later-boundary crash position cannot be reconstructed here, because it needs
a third store to exist rather than a third test. A reverse-order test varying
which store is stranded is the closest surviving analogue, and it is labelled as
that rather than as a substitute -- in the module's own docstring, where a
future reader will meet it, rather than in a commit message nobody revisits.

**One correction shrinks the loss this step was opened to repair.** The deleted
third arm's re-wrap logic lived in the test file rather than in production --
there was never a keystore rotation primitive, so the old module authored its
own probe-skip helper and then asserted that helper behaved. That arm was closer
to testing its own code than its prominence suggested, and the coverage
genuinely lost is smaller than the deletion message claimed. The correction runs
against the author's own earlier framing, which is what makes it worth recording.

Bite-proved rather than assumed: neutering the envelope probe-skip fails two of
three on the skip count, and neutering the blob probe-skip fails all three. Both
patches were loaded from outside the repository, so no tracked file was edited
and nothing was left behind, and the pair proves every test bites on at least
one probe-skip.

## Notes

A stray 566 KB profiler dump entered history alongside this work, and the
mechanism is worth recording because it is new. The author's own change had
already been swept into a peer's sweep commit, so their `git add` and `git
commit` pair found nothing of their own to stage and instead consumed a binary
someone else had left standing in the shared index -- which then entered history
wearing this step's commit message.

So the shared index does not merely risk carrying a peer's work INTO your
commit; when your own work has already been taken, it can supply the entire
contents of a commit you believed was yours. The author reported it rather than
leaving it, and it was untracked through an isolated index so that no bare
commit was needed. The file remains on disk for whoever generated it.

The author also left a staged untrack standing deliberately rather than clearing
it, reasoning that if a peer's bare commit consumed it the result would be the
correct outcome anyway. That reasoning was sound -- it is the one case where
being swallowed produces the desired effect -- and it was superseded only
because the untrack could be landed precisely instead.
