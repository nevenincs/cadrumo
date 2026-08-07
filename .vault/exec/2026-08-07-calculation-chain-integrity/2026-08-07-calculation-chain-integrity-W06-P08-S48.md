---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:26e25621879523521b487615a91b25b0d04d133fd886f051df506172f1198685'
step_id: 'S48'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S48

## Outcome

Noted where it will be read — in the parity gate itself rather than only in the vault — and the note is backed by the executable guard `S50` landed alongside it.

## The note

Splitting the annual casilla per leg requires per-leg semantic roles on the reconciliation parity gate, because the two sides will stop sharing a join key.

The gate joins on `semantic_role` rather than casilla id, deliberately: the two sides number the same concept differently, and today the annual `iva.anual.autorepercutido.intracomunitaria` and the quarterly `iva.autorepercutido.intracomunitaria` share the role `iva_cuota_autorepercutida_intracomunitaria` and nothing else.

After a per-leg split the annual side carries **two** roles where the quarterly side carries **one combined** role. Neither of the two intersects the one, so the join produces nothing for that concept.

## Why a note alone would not have been enough

A note in a vault document is invisible at the moment the split is authored. The failure mode it warns about produces no error — the intersection just gets smaller — so nothing would prompt a reader to go looking for the note.

That is why this Step's note is recorded as a docstring on `_INTRACOM_AUTOREPERCUTIDO_ROLE` and its guard, at the join site, and why `S50` makes it assert rather than describe. The note explains the mechanism; the guard makes the mechanism announce itself.

## Consequence for whoever lands the split

Two acceptable resolutions, and the guard's failure message states both rather than picking one:

- keep the combined role on both sides, so the existing join continues to work and the per-leg detail lives below it; or
- teach the gate a per-leg mapping, so a combined role on one side compares against the union of two roles on the other.

The unacceptable third option is landing the split and letting the concept fall out of the comparison, which is what happens today if nobody is looking.
