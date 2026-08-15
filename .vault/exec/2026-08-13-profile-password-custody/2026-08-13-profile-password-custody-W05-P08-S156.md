---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:c871a030851259d3263d7566ce3e0f04155a0df174162d934083e856517aa649'
step_id: 'S156'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule how open legal cases reach the application

## Scope

- `src/cadrumo/application/evidence/_profile_legal_hold.py`

## Description

- Establish where the legal-hold answer legitimately enters the system.
- Establish what the application must do while it has not entered.

## Outcome

**Ruled: "legal hold" is TWO populations, and treating them as one is the
error. Half of it is derivable from facts the application already holds; half
is genuinely external.**

**The premise this row was given is wrong for half the subject, and that is the
most useful thing in this ruling.** The row states that the recorder takes case
identifiers supplied from outside, so no refresh can close the gap. That is
true of one population and false of the other, and inheriting it unexamined
would have sent the next reader to build an operator surface for a question the
system can already answer in part.

**Population A -- AEAT proceedings, derivable today.** The application already
captures a profile's AEAT *expedientes* from the sede and persists them per
bucket. An open expediente is a live proceeding against that profile, which is
a concrete reason not to erase its records, and it is a fact the system holds
rather than one it must be told. This population is closable by the pattern
this campaign has just built: the snapshot is bucket-local, full-custody and
encrypted, so it is unreadable at a deletion preflight for exactly the reason
the filing catalogue was, and the answer is the same -- record a plaintext
owner snapshot at CAPTURE time rather than trying to read it at deletion time.
The outstanding-debt snapshot deserves the same examination for the same
reason; an unpaid liability is arguably also a reason not to erase.

**Population B -- genuinely external holds.** A court order, live litigation,
an instruction from the taxpayer's adviser. No in-system source exists and none
can be derived, so absence here means nobody has been asked rather than no
holds exist. Defaulting it to empty would fail open on the erasure of taxpayer
data, which is the one direction this apparatus must never fail.

**Where the answer enters, per population.** A is derived at capture. B
requires an operator affirmatively recording the position, and that has no
surface at all today -- the legal-case authority is exported on the application
facade and is reachable from no entrypoint whatsoever.

**What the application does meanwhile: refuse. That is a correct outcome rather
than a gap** -- a destructive action declining because a required human input
is missing is the system working. But the refusal does not SAY that. It reports
that canonical legal hold owner facts are absent, which reads as an internal
defect, so an operator meeting it cannot tell that a human input is required,
which one, or how to supply it. The refusal is right and its message is wrong,
and that is the same class as a refusal found earlier in this campaign whose
text directed the operator to a command-line option that did not exist: a
correct guard made unusable by prose nobody could act on.

## Notes

**A caution that belongs with population B rather than with its mechanism.**
The operator affirmation must not become a blanket acknowledgement recorded
once and never revisited. A hold arising after that moment would be invisible,
and the recorded fact would then be WORSE than absence: absence fails closed
and refuses, while a stale affirmation fails open while looking answered. It
needs a freshness bound, in the way the profile acceleration receipt carries a
deadline. That constraint matters more than the shape of the surface.

Recommended sequencing, recorded because the two populations have very
different risk. A is ordinary implementation work, well specified by the
existing write-time snapshot pattern, and landing it reduces how often B is
reached at all. B is a design question covering the operator surface, the
affirmation's shape and its freshness bound. The refusal-message correction
depends on neither and should not wait for them, because until it lands a
correct refusal continues to read as a bug.

Nothing was built. This row is a ruling, and both of its factual claims were
verified rather than argued: the legal-case authority has zero entrypoint
reach, and the expedientes snapshot namespace is real and bucket-local.
