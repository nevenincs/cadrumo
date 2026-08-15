---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:10633eddd712884d8b09dc14b4fe12543fc937ea445b426af4930a41bc9e77fd'
step_id: 'S118'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh re-derive every stated reason in the runtime bootstrap-exempt allowlist against the tree, since two of its justifications were found false in one day, one citing a test that was never written and one asserting a manifest read that no longer happens, and the entries were correct in both cases so the defect is that a reader inherits a false reason rather than re-deriving it, which is worse than a file carrying no comments at all

## Scope

- `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`
- `src/cadrumo/entrypoints/cli/tests/test_bootstrap_exempt_entries_resolve.py`
- `src/cadrumo/entrypoints/cli/tests/test_login_gated_verbs_never_exempt.py`

## Description

- Re-derive all 24 stated reasons against the tree, opening the thing each one cites.
- Correct the two false claims found, and remove one dead entry the previous pass missed.
- Convert every checkable claim from prose into typed record fields a gate reads.
- Replace the resolution gate's path resolver, which was rewriting the entries it checked.
- Add gates for cited verbs, cited tests, prefix subtree membership, and read-only claims.
- Prove each gate bites by planting a false record from outside the repository.

## Outcome

Twenty-four entries were carried. Every stated reason was re-derived by opening
the thing it cites, not by reading the comment. Verdicts:

TRUE, entry and reason both hold, 21 entries. `config profile create` (first-run
deadlock; the verb resolves its own session for the bucket it creates).
`config login` and `config logout` (the session doors). `config reset` (owns the
pointer transaction and journal; its status verb reads one journal without
resuming it). `config repair` (torn-state diagnostic, and it already carries a
fresh-root sessionless probe). `config profile list` (projects committed custody
capsules and unlocks nothing, so a locked profile still lists). `config storage`
(the reclaim guard refuses the durable-state areas outright, so what the verb can
reach is root-level regenerable material). `app live portals list` and `view`
(in-memory portal registry). `config auth providers` and
`config auth apoderado scopes list` (bundled catalogues). `app registry` (the
family is declared read-only in the operator-surface contract; confirmed against
the live declaration). The six `app modelo` discovery leaves. The three
`review-package verify*` leaves (they take the package, envelope and public key
from the command line; only the signing verbs touch the secure store).
`app diagnostics telemetry status`.

FALSE reason, entry correct, 2 entries. `app ledger categories`: the reason
described "the ledger pair", one of which read PATH and localhost for LLM
providers. That second verb was deleted before the previous re-derivation pass
ran, and the pass still shipped the claim; the surviving verb reads a compiled
category catalogue and nothing else. `config profile create`: the reason
asserted wizard-internal session behaviour, which is a mechanism claim about a
package another row is currently changing.

ENTRY ITSELF WRONG, 1 entry. `diagnostics` was dead. Matching is on the
operator-typed subcommand chain, which always begins `app` or `config`, and the
diagnostics group is mounted at `app diagnostics`. No dispatchable path could
ever start with `diagnostics `, so the entry was inert, and it was armed in the
same way the six S75 cleared were. Its reason was also false twice over: there is
no separate module entrypoint (the only other console script is the MCP one, and
it does not consume this allowlist), and the group is registered in the CLI's own
lazy-registration table under `app`. The note S75 recorded, that one
deliberately non-resolving entry is not a defect, does not survive re-derivation.
Removing it changes no behaviour: exemption verdicts were computed for all 282
live leaves under the old and the new tables and are identical.

The row's real point was the mechanism, and the mechanism had a defect of its own.
The resolution gate the previous pass shipped could not have caught the dead entry,
because its resolver projected a key with no `config`/`app` root onto an `app`
prefix. It therefore checked `app diagnostics` and reported the entry live. The
gate's own docstring claimed a property it did not test. It is replaced with a walk
that resolves the exact string `is_bootstrap_exempt` matches, token by token from
the root, rewriting nothing.

On whether the reasons can be made mechanically checkable: partly, and the
checkable part is now data rather than prose.

- An entry's criterion is a closed enum, so an entry cannot be admitted for an
  unnamed reason.
- A reason that leans on another verb declares it, and a gate resolves it. This
  is the class that failed with the deleted ledger verb.
- A reason that leans on a test declares it, and a gate asserts the test exists.
  This is the class that lost the login-gating principle recorded under S113.
- A prefix entry declares the descendant leaves it carries, and a gate compares
  that against the live subtree. This is the sharpest of the five: prefix
  matching means a verb registered under an exempt group is exempt the instant
  it lands, with no review, and the module's own telemetry entry was written in
  fear of exactly that. It is now a red gate naming the new verb.
- An entry claiming its family is declared read-only has that claim checked
  against the operator-surface contract.

What is not checkable is the judgement in each record's note, and the record says
so where it lives rather than asserting a fact. The first membership criterion,
that the verb answers on a fresh root with no session, is behavioural and so is
executable in principle; the recovery family already has such a probe. It was
built for the read-only classes and then withdrawn rather than shipped, for the
reason given under Notes.

Every gate was proven to bite. Ten planted records, each constructed in memory
from outside the repository so no tracked file was mutated, each red: an entry
naming an absent verb; an entry omitting its root segment, which is the exact
shape the old resolver passed; a cited verb that no longer resolves; a cited test
that does not exist; a leaf appearing under an exempt prefix; a read-only claim
contradicting the contract; and the four refusal gates recorded under S113.

Verification. The two gate modules are green: 65 passed. Lint and the canonical
type checker are clean on all three files. The wider consumer run is not clean,
and none of its failures is attributable here; see Notes.

## Notes

The behavioural probe was built and then deleted rather than shipped. Two things
made it unprovable in the current tree. Asserting no session was opened is
tautological, because the session is closed by the time the runner returns for
both an exempt verb and a profile-bound one. Asserting a clean exit couples the
session axis to unrelated tree health, and the tree is currently not healthy on
that axis: the bundled registry does not pass validation mid-sweep, and a
profile-bound verb on a fresh root does not produce a session refusal but an
internal error, because an orphan mounted family declaration crashes the
operator-surface manifest build. A gate that cannot be shown to bite is worse
than a declared gap, so the gap is declared instead. What would close it is a
signal that distinguishes a refusal for want of a session from any other failure.

Sixteen failures in the wider consumer run are not attributable to this work.
Twelve are the orphan mounted family declaration for the config passphrase family,
which raises during operator-surface manifest construction and comes from another
agent's custody sweep. The leaf-census and mutating-leaf guards name
`app ledger counterparty confirm` and eight sibling ledger and modelo leaves that
are not enrolled in any write-guard mechanism; the correct home for those is the
profile-bound write list, not this allowlist, and widening an exemption to green
a test is precisely what this row exists to prevent. One is a refusal-message text
change in the storage write policy, and one is a custody retention refusal in the
reset lifecycle. Two earlier runs also failed on a concurrent registry-write race
during cache fingerprinting, which cleared on re-run. The claim that none of these
is mine rests on the 282-leaf verdict diff, which shows the old and new tables
agreeing everywhere.

A peer's broad commit swept these files into the repository while the work was in
progress, so the changes are at HEAD rather than in the working tree. Nothing was
committed from this seat.

One claim in the row's own framing needed correcting against the tree. The test
the deleted comment cited was not "never written": it was written on 2026-08-03
in the same commit as the comment, and was lost later in a worktree
consolidation. The distinction matters, because it means the failure was not a
fabricated citation but a citation outliving what it cited, which is a failure
the cited-test gate now catches and a fabrication gate would not have.

The rule that a verb rename needs a hand sweep through the surfaces the gates do
not scan is now less true of this file: an entry naming a verb that stops
resolving, a reason naming a verb that stops resolving, and a leaf appearing
under an exempt prefix are all mechanically caught. A rename that retires a leaf
still needs the sweep.
