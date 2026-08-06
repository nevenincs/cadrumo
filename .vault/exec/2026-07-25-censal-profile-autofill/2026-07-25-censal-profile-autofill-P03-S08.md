---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:05bbd99c4acc164c03f2ce24fbafb17ca15971ae9de49ea92ea3402aeed6cba4'
step_id: 'S08'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Commit pulled facts through apply_cotejo, adopting only blank paths and reporting every disagreement

## Scope

- `src/cadrumo/application/live`

## Description

- Read the existing local-artefact censal ingestion path first and follow it as
  the template, so the live transport joins a working surface instead of opening
  a second authority.
- Add a typed reconciliation record carrying the adopted facts and the reported
  disagreements as two separate collections.
- Split a projected read against the profile record's canonical path-value
  projection: adopt where the record is blank, report where the two differ, emit
  neither where they already agree.
- Commit the split through the single cotejo apply authority, mapping each
  disagreement onto a divergence row stamped with the same provenance token.
- Export the reconciliation and commit functions from the package facade.
- Pin the behaviour with real-behaviour tests against a real encrypted profile
  record through the sanctioned write path: a blank path adopts, a matching
  declared value is neither adopted nor reported, a conflicting declared value is
  reported and left standing, the commit emits exactly one censo-applied event,
  and an operator-declared value survives a pull that disagrees with it.

## Outcome

Pulled censal facts commit through the one apply authority, and a pull cannot
overwrite what the operator declared.

Modified files:

- `src/cadrumo/application/user_profile/_censo_sync.py` — the reconciliation
  record, the blank-versus-conflict split, and the commit function.
- `src/cadrumo/application/user_profile/__init__.py` — facade exports.
- `src/cadrumo/application/user_profile/tests/test_censal_sync.py` — the
  reconciliation and commit tests.

The three-outcome split is the load-bearing part. Adopting only blank paths is
what makes the pull safe to run repeatedly; reporting rather than overwriting is
what keeps the operator the adjudicator between their own answer and the
authority's. Treating an equal value as neither adoption nor divergence keeps a
re-pull from manufacturing churn or a spurious divergence row.

Routing the commit through the existing apply authority rather than the general
field-write path is what preserves the single-event contract: one apply-commit
emits exactly one censo-applied event regardless of how many facts it carries,
and no parallel write route is opened. A test asserts the event count rather
than trusting the delegation.

## Notes

The Step row scopes this to the live application package; the work landed in the
user-profile package for the same reason as the mapping Step. The live package
holds the acquisition call only.

The provenance token this stamps was already declared and already read by the
overview calendar to decide whether censo enrolment is authority-verified, but
nothing had ever stamped it, so that branch was dormant. It is now live: a
profile carrying these facts stops raising the unverified-enrolment advisory for
censo-derived obligations. That is correct only because the consulta is an
official authority read; facts from an operator-supplied artefact or an editing
surface carry the non-official token instead and do not trigger it. This is a
visible behaviour change and was called out rather than left to be discovered.

The concurrent work enforcing the declared path and provenance sets on the fact
model landed while this Step ran. It turned the projection's path-conformance
test from a convention check into a boundary-enforced one, and its own four
failing tests and one import-boundary violation are its to reconcile; neither
touches the files changed here.

Two defects were found in this Step's own reconciliation after it first landed,
and both are recorded here rather than only in the commits, because the second
one carries a correction to a claim made during the work.

The first: the split compared values through the path-value projection, which
carries no provenance, so it could not tell an operator-declared value from one
a previous read had adopted and gave both the operator-adjudicates protection. A
value therefore went sticky once first read — an address change at the authority
produced a reported disagreement instead of a refresh, permanently — and the
reported row asserted something untrue, because both sides were the authority's,
one stale and one current. The split now reads the recorded fact's provenance:
an authority-written value refreshes, and only an operator token earns the
protection.

The second was found by probing the first fix and is the one worth reading. A
path the operator explicitly CLEARED was re-adopted on the next read. The blind
spot behind it: the design reasoned about the operator declaring a DIFFERENT
value and never about the operator declaring NOTHING, deliberately. A clear is a
declaration — the operator saying they do not want the field on their profile —
and it was the one form of declaration the value-only projection could not
express, because the store keeps one fact per path, clearing replaces the value
with an empty marker, and the projection filters that fact out, so the path
vanishes and reads downstream as never-set.

The correction: this was first reported as a regression introduced by the
provenance fix, on the strength of a probe that measured an asymmetry — the
clear surviving when the authority agreed and being undone when it differed.
That asymmetry was an artefact of the probe, which hand-built a record with two
facts at one path. The store does not behave that way. Against real persisted
state the path was re-adopted unconditionally, both before and after the
provenance fix, and so had been present since the feature first landed. The
wrong version mattered: the age and cause of a defect decide where else to look,
and "introduced yesterday" points at one commit where "the shared projection
cannot express this concept" points at every consumer of it. The probe being
wrong, rather than the system being strange, is the thing to suspect first.

Both fixes carry the guard that would have caught them. The cleared-path test is
parametrised over the authority agreeing and differing, which pins the
asymmetry that was mistakenly reported so it can never become real; and the
projection test asserts the two views DISAGREE about a clear, so a later
simplification that unified them would look like tidying and fail loudly instead
of silently restoring the defect.

The provenance-carrying projection replaced its predecessor rather than joining
it. Returning one record per path — value, source, and the cleared state
together — makes it structurally impossible for a value to be adjudicated
against a different fact's provenance, where two parallel mappings could
disagree about which fact is effective. The widely-consumed path-value
projection was deliberately left untouched: filtering cleared facts is correct
for consumers that want an effective value, and changing it to fix this surface
would have altered unrelated behaviour across the tree.
