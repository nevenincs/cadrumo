---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1caeae00385d5ae1b83dd0e7d82f53e58546a3b4c519440fee228c78b51cf053'
step_id: 'S24'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S24

## Outcome

Swept the retencion derivation surface by meaning. **Fragmented authority named**, matching the Step's premise: one concept (what was withheld, and at what rate) is split across three sites that do not consult each other.

## What the sweep found

- **The amount** is derived in `application/aggregation/_renta_income_ledger.py:813` (`_WithheldInference`), by bounded inference only — declared invoice gross minus cash received. Its own docstring is explicit that the base is never reconstructed.
- **The route that produced it** is typed separately, as `LedgerWithholdingDerivation` in `core/aggregation.py:569`, whose docstring states the load-bearing fact: "A ledger row never *declares* its retención — no transaction field records one — so every non-zero figure on this surface is derived."
- **The rate** is checked nowhere near either. `application/aggregation/_retencion_rate_advisory.py` carries `_conforms_to_fixed_rate` plus the administrador and sectoral advisories, and its module docstring records that the engine does not compute the withheld amount at all — the operator enters it — so the fixed rate could previously go unverified.
- **The destination** is the hardcoded backend-inputs override this campaign already tracks at `W01.P01.S03`.

## Assessment

Not a duplicate-authority finding: none of the three re-implements another. It is the weaker but real form — one concept with **no single owner**, so a change to how a retención is derived has no one place to land, and the amount, its provenance route, its rate plausibility and its casilla destination can each move independently.

The amount/route pair is the healthiest part: `LedgerWithholdingDerivation` is a typed enum whose member is asserted against the figure by `_withheld_derivation_matches_the_figure` (`:269`), so a derived amount cannot silently lose the account of how it was derived.

No new fix proposed here. `W01.P01.S03` already closes the destination half, and `W03.P05.S12` already narrows the advisory. Recorded so the split is visible as one shape rather than four unrelated steps.
