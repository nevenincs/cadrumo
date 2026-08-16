---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:c7f03743a59723a62fd198c2ea66e2beb175b6f3b4878874b0b4de6000b60146'
step_id: 'S206'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh turn on recovery enrollment at the profile creation door, wiring the composable enrollment mint into the create transaction so a real operator's profile is enrolled at the moment it is created, since the accepted decision places enrollment at creation and the mint lands as a primitive its consumer must call, and the single line that activates it belongs to the transaction whose ordering guarantee closed the displaced-session leak rather than to the row that built the primitive

## Scope

- `src/cadrumo/application/user_profile/_registration.py and src/cadrumo/application/user_profile/_custody_service.py`

## Description

- Wire the composable enrolment mint into the create transaction so the capsule
  is published already carrying its recovery wrapper.
- Carry the minted secret in its wipeable container and wipe it on every exit
  path, including the refused one and the one where the handover itself raises.
- Report on the registration outcome whether a wrapper was minted, so no
  surface can leave an operator unaware their one chance has passed.
- Rebuild the terminal-direct display channel the interactive command line
  needs, and pass it as the handover.
- Warn on the machine surface when no wrapper was minted.

## Outcome

Enrolment is live at the creation door. The mint runs BEFORE the create
transaction, because a committed capsule has no in-place recovery installation
path and inventing one would mean a second writer into a published capsule.

The secret never touches the returned model, an envelope, or a log. It reaches
the operator through one channel and no other: a direct write to the
controlling terminal device, bypassing stdout so a redirected stream, a JSON
envelope or a teed log cannot capture it. That channel had existed for exactly
this purpose and had been deleted; only its gravestone in two gate allowlists
survived, and rebuilding it restored a locale entry that had been left with no
producer.

Building it surfaced a failure worse than the leak it prevents. Gating on
whether the terminal device OPENS is not sufficient: Windows hands a detached
process a freshly allocated console, so the open succeeds and the write lands
on a surface nobody can see. A detached child reported a successful write. The
operator would then be told their profile is enrolled for recovery while the
only copy of the words went to a phantom console — silent loss, not silent
exposure. The channel now gates on the same predicate that decides whether a
secret may be PROMPTED for, so there is one notion of an attached terminal
rather than two, and a detached child refuses.

Where there is no interactive terminal the handover is absent, the door mints
no wrapper AT ALL, and the run emits a warning stating that the passphrase is
now the only way in and recovery cannot be added later. Minting a wrapper whose
words were never displayed would be worse than minting none: the operator holds
a profile they believe is recoverable and nothing that can recover it.

## Notes

**DELIVERED NARROWER THAN THE STEP ASKS, AND THE GAP IS LOAD-BEARING.**

The Step's standing goal is that a real operator's profile is enrolled at the
moment it is created. That is now true of the command line and NOT true of the
full-screen interactive surface, which passes no handover and therefore mints
no wrapper at all. That surface is the primary interactive creation door, so
the operator best placed to write down a recovery phrase is currently the one
who does not get one — and because recovery can only be installed while the
capsule is being published, every profile created that way is permanently
unrecoverable.

The remaining work is not a wiring line. The terminal-direct channel is the
wrong instrument inside a full-screen application, whose display it would
corrupt; that surface must show the words itself, and the wipeable container
must be threaded through rather than the plain string, or the wipe primitive
can no longer reach the secret.

Deferred by operator decision: that surface is blocked behind unrelated
architecture work. This row is therefore recorded as carrying a known
carry-forward rather than as delivered in full.
