---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:af406d2abfb72bd07672fbb5a7b29d74c877eadf8f7ff2ea1880cb2735c2487a'
step_id: 'S91'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule on the overloaded session vocabulary that caused a wrong architectural premise to survive two rounds of review

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_persisted_session.py and src/cadrumo/adapters/outbound/aeat/auth/_session_store.py and src/cadrumo/application/auth/`

## Description

- Establish how many concepts actually share the word before proposing a rename.
- Decide which concept keeps it, grounded in the naming rule rather than in
  preference, and price the change honestly.
- Gate the split in both directions so the collision cannot reform.

## Outcome

**It is three concepts, not the two the row describes, and the third is the one
that caused the misreading.** Inside a single module, "session" names the profile
acceleration receipt in the keystore sidecar outside the encrypted store; the
live in-process key holder with no durable existence; and the authority browser
session as an encrypted row inside the bucket. The module's own opening docstring
uses the word for two of them IN ONE SENTENCE. So this was the defect's own
mechanism one level down rather than only a reviewers' problem.

Measured rather than asserted: a hundred and sixty-four session-bearing
definitions, a hundred and nine already qualified, fifty-five bare. Nearly every
symbol was already unambiguous and a sweep over those would have bought nothing.
The genuine collision is ONE phrase used bare by both sides, plus four test
modules split across two custody classes under one name -- the same shape this
project's naming rule already records for a reserved term.

**The ruling: the authority session keeps the word because it IS one** -- a
counterparty, a protocol, cookies, and four locale catalogues already saying so
to operators. **The receipt yields because it is not a session at all**: no
counterparty, no protocol, a locally held wrapped key with a deadline. The
deciding evidence is that the code ALREADY called it a receipt eighty-four times,
so the rename adopts the codebase's own prose instead of inventing vocabulary.

**The full sweep was declined with the numbers to justify it**: roughly
twenty-four hundred occurrences across forty-one production modules, which the
relocation rule would force into a single commit, in a tree where several
campaigns commit continuously. The landed scope fixes the one bare phrase both
sides share and the four ambiguous test modules, and leaves some twenty-three
hundred already-qualified occurrences alone.

Verified independently: the renamed roundtrip suite is 23 passed and the new
bidirectional gate is 10 passed.

## Notes

**The gate's scoping is the sharpest judgement in the work.** A first version
reddened on local variables and persisted field names, and was narrowed to the
module-level named surface -- because a local is never read outside its own body,
and a field name is WIRE FORMAT bound into the record's authenticated data, so
renaming it would have been a wire change smuggled in under a naming rule. The
same distinction the author drew for the keychain service token, applied one
level down, and easy to miss on the way to a green gate.

One rename beyond the approved list was taken rather than exempted: a bare
window-name on the receipt side is now qualified with the bucket, because under
the ruling an unqualified "session" there means the live bucket session, so the
name should always have said so. Exempting it would have taught the gate to
tolerate the exact ambiguity it exists to refuse.

Two deferrals are recorded IN THE CODE rather than only in the plan, where
whoever needs them is reading. The operating-system keychain service token keeps
its old name deliberately, with the reason at its definition: it is an identifier
outside our storage root, so renaming it would strand credential entries that
deleting the storage root cannot reap, and writing deletion code for the old
token would be exactly the migration shim the compatibility rule forbids. A wire
identifier is not an alias, because it is not a second code path to the concept.
The storage-taxonomy segment carries a named condition that it rides the
authorised destructive local reset.

**The change was landed in two commits because the dispatcher split it.** The
work sat uncommitted in the most exposed shape available in this tree -- two
deletions plus an untracked file, author idle -- and the dispatcher verified and
landed the code half to rescue it, taking five files and leaving three
regenerated documentation stubs behind. That orphaned a stub for a deleted
module, which hard-crashes the strict documentation build rather than degrading
it, until the author landed the remainder.

The lesson is recorded because it refines the habit this campaign relies on:
**reading your own commit's stat line detects taking too MUCH and is structurally
blind to taking too LITTLE.** The stat line matched the dispatcher's intent
exactly. When landing anyone else's change the question is not whether something
was taken that was not yours, but whether everything that belongs together was
taken -- and for a module-tree change this project has an explicit same-commit
rule for the regenerated stubs.
