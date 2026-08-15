---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:3a6eee6b569f3023da703534a0b5e6ac31974f79eb8bd6ff8ce0646ae6c49bf9'
step_id: 'S174'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh repair the interrupted-handover recovery that refuses a second profile registration in one process, since the pointer is judged against two witnessed handover states and matches neither on an ordinary sequential registration, so every surface that must stand up two live profiles is blocked including the whole duplicate-label ambiguity refusal suite, and the failure reproduces in test modules that were never touched by the manifest retirement

## Scope

- `src/cadrumo/application/user_profile/_login_session.py and src/cadrumo/application/user_profile/_profile_pointer_transaction.py`

## Description

- Measure the pointer and both witnessed handover states at the moment of the
  refusal, from outside the repository, before forming any conclusion.
- Classify the terminal receipt by its phase, before the pointer is consulted.
- Fold the completed handover's selected profile into the retirement union,
  because recognising the receipt unblocked a flow that then leaked.
- Prove the non-recoverability property across separate processes and prove the
  repair bites in both directions.

## Outcome

**Explanation (a) held: the guard's model of legitimate states was incomplete,
and the pointer was not inconsistent.** The measurement decided it. Instrumenting
the classifier from an out-of-repo pytest plugin, the second login sees a pointer
naming the freshly registered profile, and a retained journal at the TERMINAL
phase whose two witnessed states both name the first profile. It matches neither,
so the guard reports an interruption. The journal it is judging records a handover
that RAN TO COMPLETION: the terminal receipt is written only after the retirement
has already executed, so there is no such thing as an interrupted terminal
handover, and the two pointer states it witnessed answer no question that is still
open. The receipt is retained past its own completion purely so ONE later login
observes the boundary, and in that interval the pointer legitimately moves:
creating a profile compare-and-swaps the pointer onto the new capsule inside the
create transaction's own durable journal. That is a well-formed, first-class
pointer transition, not an inconsistency, which is what rules out (b).

The repair therefore classifies the terminal phase FIRST, before the pointer is
read at all, and every pre-terminal phase keeps the pointer judgement and keeps
failing closed exactly as before. The refusal string, its context and its
fail-closed behaviour are unchanged.

**Recognising the receipt was not sufficient, and the second half is the more
serious finding.** With only the phase-first classification the flow proceeded and
the retired profile's thirty-two byte bucket key was recoverable with no
passphrase, measured across separate processes. The cause is the same
observation-completeness defect the closed union row identified, in a case that
row had no way to see: in a fresh process the live session is absent, and the
durable pointer captured at login names the profile being ENTERED rather than the
one being left, because the registration already moved it. Both observations are
blind, and the interrupted-handover witness is absent because nothing was
interrupted. The only remaining durable source is the completed handover's own
record of which profile it selected, so that is folded in as a fourth observation.
The exclusion of the candidate is preserved unchanged, since revoking there would
destroy the receipt the same login just minted.

This ordering matters and is worth stating plainly: the narrow repair, landed
alone, would have converted a refusal into a passphrase-free key recovery. It was
caught because the property was measured on recovered key material across
processes rather than assumed to be untouched.

**The separate-process proof.** A new suite registers a profile, logs into it in
its own interpreter, registers a second, and logs into that in another
interpreter, then asks the production resume authority for the first profile's
material from a third process. It returns nothing, with the typed absent refusal.
Its anti-tautology arm proves the same probe returns the full thirty-two byte key
while that profile is the selected one, so the refusal cannot pass merely because
a separate process cannot reach the material.

**The two-way bite proof.** Two defect injections, both from outside the
repository through a startup hook that reaches spawned children as well as the
test process, since a plugin alone never reaches a spawned login. Reverting the
terminal-phase recognition reds exactly the four sequential-registration cases and
leaves the interrupted-handover refusal green, reproducing the pre-repair baseline
exactly. Dropping only the completed-selection observation reds exactly one case,
the cross-process proof, and it reds on the recovered key material rather than on
a reported outcome. Each injection reds what should react and leaves the rest
alone.

The control module the dispatcher used to establish the defect went from three
failures to one, and that one no longer touches this defect: it drives
`config profile delete`, a verb that no longer exists on the CLI surface.

## Notes

**The topology difference is why the existing handover suite never saw this.**
That suite registers every profile it needs before its first login, so the pointer
only ever moves inside a login's own handover and the retained terminal receipt
always still matches one of its own states. The operator flow interleaves
registration and login, which is the one arrangement that moves the pointer
between a completed handover and the next login. This is the same lesson the
re-siting row recorded, in a second dimension: a proof inherits not only the
process topology it is written in but the operation ORDER it is written in.

**A history search did not find an introducing commit, and the reason is
structural.** The classification and the refusal string are original to the
journal's introduction; nothing in the three recent commits on the module altered
the classifier. The state was simply never reachable from the suite's own setup
order.

**An adjacent finding, not fixed here and outside this row's ownership.**
Registration selects the newly created profile by compare-and-swapping the
pointer, and retires nothing. Before this repair the consequence was masked
because the next login refused outright. The retirement union now covers the
login that follows, but the window between the registration and that login is
still one in which the displaced profile holds a resumable receipt, and a
registration that is never followed by a login leaves it standing. Whether
creation should retire the profile it displaces belongs to the create
transaction's owner, not to the login session.

**Two unrelated red results, attributed rather than absorbed.** The full
login-handover suite ran twenty-seven passed and one failed, and the failure was a
spawned child dying on a name error inside another package that a peer was editing
mid-run; that import has since landed and the case passes. Re-running the crash
matrix afterwards failed two different parametrisations, then passed both on a
third run with no code change in between: the crash watcher compares the observed
phase and then calls the exit, and the remaining handover work can still finish
inside that window on this share. That flake is pre-existing, is documented in the
closed union row as partially addressed, and is independent of this change, which
alters nothing on that path. The import-hygiene gate is red tree-wide, at one
hundred and three sites against a documented sixty-nine; no entry names the new
module, its imports are intra-package, and the debt list carries no entry from
this test package at all.

**The plan row is deliberately left open.** No checkbox was set, and this session
ran no git write of any kind. The changed files nevertheless reached the branch
inside a peer session's broad sweep commits while the verification runs were still
in progress, which is the same working-tree capture the session-receipt row
recorded. The landed content was re-read afterwards and is intact: the classifier,
the fourth observation and the new suite are all present and unmangled. As with
that earlier row, the condition that a custody fix be legible in history under its
own description is not met, and this record carries the account instead.
