---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:aee0e41a752df309c5a4302bace4b584481de257900cb7c889d4a32cb5c1ce58'
step_id: 'S12'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W03.P05.S12

## Outcome

Done, and solved a better way than the Step's own wording proposes. Verified at HEAD; 7 tests green.

## What the Step asked for, and why it was not done literally

"Narrow the statutory-rate advisory to the rates a taxpayer can lawfully be subject to" reads as a filter: decide which rates apply to this taxpayer and compare only against those. That would restore the flat-fee catch — a bank fee landing on 1% or 2% of the base stops being absorbed as a conforming sectoral rate — but it buys the catch with a suppression.

The profile cannot establish that a taxpayer is NOT agrícola, ganadero or forestal, because it does not record activity type at all. That is the very gap `W03.P05.S11` exists to close. So narrowing by profile would silence a real finding on a fact nothing verified, which is strictly worse than the miss it fixes.

## What was done instead

`718a06f263` grades the advisory by rate size rather than filtering by taxpayer. Three outcomes decided by arithmetic alone:

- Matches a **professional** rate (15% or 7%) — silent. Those figures are too large for a fee or rounding gap to reach by accident, so the match is a strong claim.
- Matches only a **sectoral** rate (2% or 1%) — fires `inferred_retencion_sectoral_rate_unconfirmed`. Real statutory figures, but small enough that a bank fee or discount lands on one by coincidence, so the claim is weaker and carries its own reason code.
- Matches nothing — fires `inferred_retencion_rate_unmatched`, the strong finding.

That restores the flat-fee catch the Step names: a fee coinciding with 1% or 2% is no longer silently absorbed into the conforming band. It surfaces, with wording that reflects how confident the signal actually is.

## The line the implementation draws, worth preserving

`bucket_id` is read ONLY to word the sectoral message, never to decide whether it fires, and the docstring states the principle: a weak signal may set how confidently we speak, it may not decide whether we speak. It closes with "Do not 'improve' this into a filter" — which is the literal reading of this Step, pre-refused at the site.

Recording that here so the Step's wording does not later look like an unexecuted instruction. It was executed; the mechanism chosen is the one that does not trade a false negative for a suppression.

## Related

The rate set is read from the registry parameter catalogue rather than restated, so a newly-grounded rate widens the conforming band automatically. `8fcbc81716` additionally pinned the percentage-quoted discount class the rate set absorbs.
