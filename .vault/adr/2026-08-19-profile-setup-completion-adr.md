---
tags:
  - '#adr'
  - '#profile-setup-completion'
date: '2026-08-19'
modified: '2026-08-19'
body_schema: 'body-v1'
body_hash: 'sha256:fbc1f6d52df1c19462ae32b160a348ee13d670073fa10d2783e6fac4e9ebe2e9'
related:
  - "[[2026-08-19-profile-setup-completion-research]]"
---
# `profile-setup-completion` adr: `profile setup completion is an explicit operator act` | (**status:** `accepted`)

## Problem Statement

No profile can reach `setup_state = COMPLETE` in production, so every modelo verb
gated on it is unreachable and the CLI's own local finish line — calculate,
verify, export — cannot be entered at all.

The transition is not missing. `ProfileRecordRepository.complete_setup` exists,
compare-and-swap guards itself, refuses to promote a record that is not actually
complete, and is exercised only by tests. The capability is built and unwired,
which is the same shape this project has already been bitten by in the
aggregation mesh: a safety net whose only caller was a test.

## Considerations

Two authorities currently disagree about the same profile. The computed
field-level check in `_completeness.py` reports nothing missing while the stored
enum still says incomplete, and `config profile show` prints both at once —
`record_validity valid issues=0` beside `setup_state incomplete`. Any resolution
has to say which one a gate may read.

The dead end is also actively misleading rather than merely blocking.
`config profile edit --quiet --accept-defaults` exits 0 and prints
`Siguiente: aeat app modelo work create`, the verb that then refuses on the state
that command did not advance. An operator following the CLI's own guidance loops,
and an autonomous operator retries.

Birth-incompleteness is deliberate and must survive any fix.
`_scripted_registration.py` states the reason: a profile is born incomplete on
purpose so a rejected fact leaves a correctable profile rather than nothing. The
wizard's checkpoint store depends on the same thing, treating `INCOMPLETE` as the
state a resumed session is resumed from.

## Considered options

**Let the modelo gate read the computed completeness instead of the stored enum.**
Rejected. It would open the gate today, but it makes the stored state decorative
while leaving it in the record, and it discards what the enum uniquely carries:
that an operator has *declared* the profile ready, distinct from the fields
happening to be populated. It also silently deletes the wizard's resume semantics,
which key on `INCOMPLETE`.

**Complete implicitly at the end of scripted create/edit.** Rejected as the
primary route. It is the smallest diff and it is safe in the narrow sense — the
transition self-guards, so no false `COMPLETE` can be written — but it makes
creation a completion authority, which `_scripted_registration.py` explicitly
says it is not, and it removes the operator's own act by inferring it from a flag
combination whose purpose was to avoid prompting.

**Carry completion on its own explicit verb.** Adopted. Completion becomes a
named act under `config profile`, available to a scripted operator, refusing with
the computed missing-field list when the record is not in fact complete. Creation
keeps its documented birth-incomplete semantics, the wizard keeps `INCOMPLETE` as
its resume state, and the stored enum keeps meaning "an operator declared this
ready" rather than "some fields are populated".

## Constraints

The self-guard is load-bearing and must not be bypassed:
`reject_invalid_profile_facts(..., require_complete=True)` stays inside the
transition, so the verb cannot promote an incomplete record however it is invoked.
A refusal MUST name the missing paths from `_completeness.py` rather than a bare
"incomplete", per the CLI contract's rule that a late refusal lists its accepted
or missing set.

The verb is idempotent: `complete_setup` already returns the current record when
the state is already `COMPLETE`, so a retry is a no-op with no second record
revision and no re-stamped timestamps.

`config profile edit`'s next-step line MUST stop naming `work create` while the
profile is still incomplete. Pointing an operator at a verb that refuses is the
defect that made this reachable-looking, and fixing the state transition without
fixing the guidance leaves the loop in place for anyone whose record is genuinely
missing a field.

## Implementation

Not implemented by this ADR, and the ADR does not pretend otherwise. The
implementing rows are: a `config profile complete-setup` verb wired to
`ProfileRecordRepository.complete_setup`; its refusal projecting
`conditional_profile_missing_required` / `missing_required_field_paths`; the
`profile edit` next-step line made conditional on the resulting state; locale
entries in all four catalogues for the new verb's help and refusal; and a
regression that drives a scripted profile from creation through completion to a
successful `work create`, which is the assertion that would have caught this.

An ADR ruling on code is not self-executing, and at HEAD `complete_setup` still
has no production caller.

## Rationale

The distinction worth preserving is between a record whose fields are populated
and a taxpayer who has said their profile is ready to file from. The computed
check answers the first; only a declared act answers the second. Collapsing them
would make the gate cheap to open and would remove the one signal that separates
a half-filled draft from a profile someone stands behind — in an application whose
whole posture is that filing-grade state must be declared rather than inferred.

## Consequences

Until the implementing rows land, the calculate-to-export path remains unreachable
for every profile, so queue item 6 — per-modelo input-to-export verification
against real exported bytes — cannot be attempted end to end. Ledger data,
readiness reporting and the registry side are all reachable and were verified
working; the wall is precisely this gate.

Once landed, a scripted operator can go from `profile create` to `work create` in
one documented sequence, and a profile that is genuinely missing a field gets a
refusal naming the field instead of a next-step pointing at a verb that refuses.
