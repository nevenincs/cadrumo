---
tags:
  - '#adr'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:d321d0a8b94a8eb8fade817a630cb1bf1c79177233c0c05f88fc68a740f83807'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - '[[2026-08-13-profile-password-custody-research]]'
  - '[[2026-07-09-compatibility-lifecycle-audit]]'
---
# `profile-password-custody` adr: `nested persisted format boundary` | (**status:** `accepted`)

## Problem Statement

The persisted-format inventory has never stated a boundary for one recurring
question: when a shape lives inside, alongside, or is produced from an
already-enrolled persisted structure, does that shape need its own entry, or
is it covered by its container's? The question has been answered three times
by three different working sessions, each from a different angle, each
argued from first principles rather than from a named test. Three new
candidates now need the same call: a per-owner hold-evidence record, a
legal-hold case snapshot, and a filing-retention snapshot, each carrying its
own `schema_version` field, each written to its own file underneath a
directory-shaped storage category the inventory's file-enumeration cannot
see. Without a stated boundary, each candidate would again be argued from
scratch, and the next one after it, indefinitely.

## Considerations

- The three prior local answers were never told apart as answering two
  different questions, and treating them as one has made each look like a
  fresh judgment call rather than an application of a rule.
- A durability floor frozen on a container proves only that the container's
  own envelope decrypts or parses; nothing about that proof extends to a
  record grammar living inside it, which is exactly the gap that let four
  taxpayer registers hide behind an "already inside an enrolled container"
  excuse.
- A field that merely restates a number another declaration already owns is
  a duplication hazard, not a second format; conflating the two questions
  either wrongly enrols a duplicate as a second format or wrongly excuses a
  genuine second format as duplication.
- Some candidates are durably written but only ever recomputed fresh from an
  already-durable source and never trusted on read, which is a different
  fact from being durably read back and should not be collapsed with it.

## Considered options

- **Leave the discriminator implicit, argued per candidate.** Rejected: this
  is the status quo the row exists to fix, and it is why the question kept
  recurring instead of resolving.
- **One-part test: independent version declaration only.** Rejected on its
  own: it enrols a duplicate literal that merely restates its container's
  number as if it were a second format, contradicting the resolution reached
  for the bundle and fincas duplicate-declaration cases.
- **One-part test: durable readback only.** Rejected on its own: it would
  fold an independently-versioned nested grammar into its container simply
  because the container's bytes are also durably read, missing exactly the
  profile-record and taxpayer-register class of gap the binding gate exists
  to catch.
- **Two-part conjunctive test: independent grammar AND durable readback of
  the shape's own bytes, each stated as an explicit, separately-answerable
  question.** Chosen. It reconciles all three prior local answers without
  reopening any of them, and it gives each future candidate two small
  questions instead of one open-ended judgment call.

## Constraints

- The ruling must not require fabricating an old-version fixture or an
  upgrader for a version nothing has written; the compatibility regime is
  `PRE_RELEASE` and stays floors-chase-current, so the boundary governs
  format-hood and classification eligibility only, never lineage obligations.
- The ruling must not itself enrol the three named candidates into
  `PERSISTED_FORMATS` or the binding gate's tables; that decision, including
  each candidate's durability class, is downstream work this record only
  unblocks.
- `COMPATIBILITY_REGIME` and its enforcing gates are untouched; this decision
  changes only how a persisted-format candidate is recognized, not the
  regime-switch machinery around it.

## Implementation

The boundary is recorded as a documented, two-part conjunctive test on the
`PersistedFormatClass` section of `compatibility_lifecycle.py`, immediately
before the enum it governs, so it sits in the one module every enrolment
decision already reads rather than in a test-file comment a future author
might not open.

**Part one, independent grammar:** a nested shape earns its own entry only
when it declares a version distinct from any enclosing container's or
envelope's version, such that a reader needs that shape's own version - not
merely the container's - to interpret the bytes. Two declarations that never
diverge and are never independently compared state one format's version
twice, not two formats; ownership of the single surviving declaration goes to
whichever side is actually exercised on the live write path, not to an
a-priori layering preference, which has lost against evidence every time it
has been tested.

**Part two, durable readback:** the shape's own bytes - not a digest, a
boolean, or another derivative of them - must themselves be written to
persistent storage and meant to be parsed back through that grammar by a
real read path, or be the sole surviving evidence of an otherwise
unreconstructable fact. A shape that only ever lives in-process and folds a
digest into some other persisted structure, discarding its own instance,
has nothing on disk this inventory needs to guarantee readable. A shape that
clears this bar by being durably written but is always recomputed fresh from
an already-durable authoritative source, never trusted on read, still
enrols - format-hood is not defeated by being a cache - but that same fact
argues for a `REGENERABLE` rather than `DURABLE` classification downstream.

Both parts must hold for a distinct entry. Failing part one alone does not
exclude a shape durably read back under its own grammar. Failing part two
means there is no format to enrol at all, independent of how part one
resolves.

Applied to the three named candidates:

- The legal-hold case snapshot (`application/evidence/_profile_legal_hold.py`)
  declares its own `schema_version`, is not embedded in any other shape's
  bytes, is written as its own file, and is loaded back through
  `model_validate_json` on every hold projection. Both parts hold: **enrol.**
- The filing-retention snapshot (`application/filing/_profile_filing_retention.py`)
  has the identical shape and the identical answer for the identical reason:
  its own `schema_version`, its own file, read back through
  `model_validate_json` on every assessment. Both parts hold: **enrol.**
- The custody hold evidence (`ProfileCustodyHoldEvidence`,
  `application/user_profile/_custody_hold_models.py`, written by
  `_custody_hold.py`) declares its own `schema_version`, independent of both
  the transaction and receipt containers it never rides inside - only a
  derived boolean and a digest travel into those. Its own bytes are durably
  written to their own per-owner, per-profile file. Part one and the loose
  form of part two both hold, so it **enrols** - but nothing in the
  production tree ever loads that file back through its typed grammar; the
  owning `refresh()` call unconditionally recomputes the evidence from the
  legal-hold and filing-retention snapshots above and overwrites the file
  every time. That is the same shape as the already-ruled participation
  index: a derived, always-recomputed read-side artefact whose own governing
  rule makes delete-and-rebuild the correct response to an unreadable
  version. It clears format-hood on durable readback in the loose sense
  (bytes exist), but the classification question downstream should weigh
  this fact toward `REGENERABLE`, not `DURABLE`.

No candidate stays out; all three clear both parts of the test. The value
delivered is not a rejection but a named, two-part reason each can now cite
instead of re-deriving from proximity.

A stale entry in the persisted-format literal-inventory gate
(`tests/test_persisted_version_literal_inventory.py`) was found and fixed
while grounding this record: an already-retired record class remained
enrolled in that gate's table and its anti-tautology fixture, failing the
gate on an unrelated axis. The entry and its synthetic proof were retired
together with the format, in the same discipline this record states for
every future format retirement.

## Rationale

The two-part test wins because it is the only option that reconciles all
three prior local answers without reopening any of them. The
independent-grammar half is exactly what the first two local answers already
argued from proximity - a container's floor does not cover a grammar living
inside it - now named as a reusable test rather than re-derived per
candidate. The durable-readback half is what the third pair of local answers
were actually doing when they resolved a duplicate-declaration case by asking
which declaration is live on the write path rather than which layer a
convention prefers; making that the second half of the same test, rather than
leaving it a separate ad hoc resolution, is what stops the next
duplicate-declaration candidate from being misread as a proximity case.
Splitting the single implicit question into these two explicit ones is the
knockout: neither half alone reproduces all three outcomes, and the
conjunction does.

## Consequences

- Downstream enrolment rows can now cite a two-part test instead of arguing
  format-hood from scratch; the three named candidates are pre-answered as
  "enrol", with the custody hold evidence pre-flagged toward `REGENERABLE`
  for the classifying row to confirm or overturn on its own evidence.
- The distinction between "is this a format" and "which of two declarations
  for one format is canonical" is now separable; a future duplicate-literal
  case need not be misdiagnosed as a missing-enrolment case or vice versa.
- Pitfall: the durable-readback half depends on reading the real call graph,
  not on a typed fact the compatibility-lifecycle predicates can check
  mechanically the way the regime-switch predicates do. It stays a
  documented human test, applied the way the binding gate's hand-maintained
  tables already are, rather than a new pure predicate function.
- A CLI test module (`entrypoints/cli/tests/test_active_profile_env_override_name.py`)
  was found, while grounding this record, to still construct the same
  retired manifest record inside a deferred import a collection-only run
  cannot see; that regression is unrelated to the boundary this record rules
  on and is left for the row that owns the manifest retirement.
