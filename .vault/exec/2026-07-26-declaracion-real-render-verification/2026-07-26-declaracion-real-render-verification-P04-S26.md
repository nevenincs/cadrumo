---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:425894110e1d26871b02d22928a9920e10f7ac23fcb120be5b81d300ce64eb25'
step_id: 'S26'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Anchor numeric_casilla on form_number rather than record-design number, closing at scale the same defect D1 corrected for the blank-box guard

## Scope

- `src/cadrumo/adapters/inbound/declaracion`

## Description

D1 established that the printed box number is `form_number` and that `number` is
reviewed AEAT record-design metadata. It was applied to the blank-box guard,
which was the consumer a real render had exposed. The other consumer was missed:
`_numeric_casilla_anchors` took its anchor from the same wrong field.

The two consumers fail differently, which is why this one stayed hidden. The
guard's failure is loud in its consequence -- a blank box returns its own box
number as a monetary value. This one is quiet in both mechanism and consequence:
`numeric_casilla` anchors on the printed number at line start, so a wrong anchor
matches nothing and the target simply drops out of every extraction, with no
error raised and only the coverage floor able to notice.

It surfaced while assessing the structural remedy for the render-language route.
The recommendation there is to migrate `named_label` targets to box-number
anchoring, because AEAT translates labels and does not translate numbers -- and
that migration would have re-opened, at scale, the defect this campaign had just
closed.

## Outcome

`_numeric_casilla_anchors` now prefers `form_number`, falling back to `number`
only when it is a plausible printed box number, exactly as the guard does.

Nothing is mis-anchored today and nothing changes. All 22 `numeric_casilla`
targets in the registry carry a numeric `number`, and the fix alters zero live
anchor values, measured across every `declaracion_pdf` profile. That is the same
accident that carried the guard until a real render exposed it, so this is a
latent hazard closed rather than a live defect fixed.

A missing printed number now refuses rather than anchoring on whatever `number`
holds, and the refusal names the record-design value it declined to use. This is
deliberately stricter than the guard, which is left lenient: a guard without a
printed number loses a safety net, which is tolerable, while a `numeric_casilla`
target without one cannot be addressed at all -- a registry-integrity error of
the same kind as a target naming a casilla that does not exist. The function
already refused that case, so the two now behave alike.

Falsifiability was proven rather than assumed. A new module drives the real
production function with real casillas from real revisions, chosen as the shapes
the accident does not cover: Modelo 390's totals, whose `number` is their own id
string, and Modelo 190's resumen summaries, whose `number` is a fichero-BOE
positional range. Reverting to the pre-fix behaviour fails all four cases, each
naming what it would have anchored on -- the id string against a printed 64, and
`145-160` against a printed 02. A fifth case pins the refusal.

The expected values are the numbers the bundled AEAT renders print, not values
read back from the casillas under test.

## Notes

The subjects are constructed profiles over real registry data rather than real
profiles, because no registry profile currently pairs `numeric_casilla` with a
semantically-named casilla -- that pairing is the hazard, not the present state.
The alternative would have been to wait for the defect to become reachable, which
is what happened the first time.

Recorded for whoever takes the language-route migration: this fix is a
precondition, not a nicety. Box-number anchoring is the only structural remedy
that route has, and before this change adopting it on any semantically-named
casilla would have produced a silent absence.

The semantic code index was truncated throughout, roughly 1027 chunks against
roughly 4546 files, while reporting itself healthy. No semantic result was relied
on; the 22-target census and the zero-change measurement both come from loading
every revision through the registry authority.
