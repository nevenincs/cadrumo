---
tags:
  - '#exec'
  - '#iva-service-localisation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:b2a1bb3fecaca38dacdc0ccb7d62a12efccf63c1933277b4e461f8614f183d74'
step_id: 'S05'
related:
  - "[[2026-08-12-iva-service-localisation-plan]]"
---

# Gate both under-declarations the fork closes, each as a mutation proof that reds against the pre-change row: a B2C service to a third-country consumer, and a B2C service to a consumer in Canarias, Ceuta or Melilla, which art 69.Dos expressly carves back out of its own exception by naming those territories. Keep a positive control on the B2B limb through the same territories so the case cannot pass by refusing everything, and assert the outcomes rather than any localised message text

## Scope

- `src/cadrumo/domain/iva/tests/`

## Description

- Gated the B2C limb through all three territories outside the Comunidad.
- Added the mutation proof: the row's former establishment-only predicate,
  restated beside its cases, matched every one of them.
- Pinned the Canarias / Ceuta y Melilla case on art. 69.Dos's own carve-back
  sentence, which names those territories expressly.
- Kept the B2B limb as the control, through the same territories and through
  both business statuses.
- Covered the two conditions art. 69.Uno does not place, which reach neither
  limb.

## Outcome

Done. 16 cases pass.

The control is the part worth naming: a suite proving only that the B2C cases
are refused would pass just as well over a row that refused everything, so the
B2B limb runs the same three territories and asserts the not-subject outcome it
always had.

## Notes

The former predicate is RESTATED in the test rather than imported, and that is
the design rather than a shortcut. The shipped row no longer has that shape, so
there is nothing to import; and a case that cannot show the old shape matching
what the new shape refuses demonstrates only that something changed, not that
this change is what bites.

Both business statuses are covered because art. 69.Uno.1.º asks for an
*empresario o profesional que actúe como tal* and says nothing about
registration. Keying the B2B limb on a valid IVA number would push every
unregistered business into the taxed branch -- the mirror of the error being
fixed, and equally invisible.
