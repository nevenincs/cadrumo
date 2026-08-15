---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:978952012c33a2ac06d91b902418f31dd46edad4d038b51b83e5bdeb04a16c0a'
step_id: 'S77'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule on the four error classes that are defined, exported and registered but never raised anywhere in production, taking the retention-floor refusal FIRST and separately

## Scope

- `src/cadrumo/application/config_reset.py and src/cadrumo/domain/retention/`

## Description

- Give the retention-floor refusal a raise site, at the point that matters.
- Prove the message renders with both interpolated values.
- Correct the dormancy docstring whether or not the raise site lands.

## Outcome

The refusal is reachable, renders, and is proven. It was defined, exported,
registered and translated into four catalogues with statute-citing text, and
nothing raised it — so the guard this campaign has been protecting all day did
not exist.

**Where the raise site went is the decision, not whether one exists.** The
delete loop walked from "this target exists" straight to prepare, confirm,
delete, and never consulted the target's retention. The only thing keeping a
retained target out of that loop was a pause in an earlier phase. The guard now
sits **at the point bytes are destroyed** — because a guard living only in an
earlier phase is one refactor away from being skipped, and what it permits is
unrecoverable. It refuses when the recorded decision blocks erasure and no
override was approved, and lets an approved override through: a floor, not a
wall.

**The rendering proof found a second defect and it is the sharper one.** The
message told the operator to re-run with an option **that does not exist** —
the CLI declares a differently-named flag. So once reachable, a statute-citing
refusal would have named a real law and then handed the operator a dead
instruction, in all four languages. Corrected in every catalogue through the
owning CLI rather than by hand, and the test now asserts the rendered text names
an option the CLI actually declares.

The proof asserts the property rather than one language's prose, after a
correction the author had to make: the first version asserted English wording
and failed because the environment renders Spanish. The message was right and
the assertion was parochial. It now asserts both placeholders resolved into the
headline, the statute present, and the real flag named — invariants across all
four catalogues.

Bite-proved: neutering the guard fails the refusal test while both
permit-through tests still pass, so the test proves the refusal FIRES rather
than that a function was called. Verified independently at three passing, with
the reset module showing its same six pre-existing failures unchanged in cause —
so the guard does not fire in the sanctioned flow.

## Notes

The docstring states plainly that no supported flow reaches this guard today.
That is what a backstop is, and it is why the proof forges the state the earlier
pause prevents rather than pretending the sanctioned path can produce it — the
same shape as the label-collision fixture, where a backstop against a state
every writer prevents cannot be tested without constructing it.

**The dead flag is the harness rule appearing in a locale catalogue.** This
project already requires that operator-facing documents cite only verbs the live
surface declares, because a citation to a renamed verb hands the agent a dead
instruction it cannot recover from. The same failure had occurred inside the
translated refusal text itself, in four languages, on the one message whose
authority comes from naming a statute — and it was invisible because nothing
raised the error, so nobody had ever read the rendered output.

The dormancy docstring is corrected independently of the raise site. It claimed
a manifest-level surface cannot decrypt the profile record and therefore cannot
assess retention; the filing authority assesses from a plaintext snapshot with
no decryption at all. That is the fourth deferral this campaign has found
describing a constraint since lifted, and this one outlived its constraint long
enough to be read as current more than once.

Scope was held to the retention-floor refusal alone. The other three unraised
error classes have a different justification and must not ride on this one's.
