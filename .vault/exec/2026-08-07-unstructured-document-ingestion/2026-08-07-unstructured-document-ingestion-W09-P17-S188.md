---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:7016d524c778910bf52f7a3f166d3da58f01600dfc10fc6b73eaffd501410aae'
step_id: 'S188'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Widen the concordance signal beyond its single source

## Scope

- `src/cadrumo/application/ledger`

## Description

- Split the concordance predicate into two named limbs, so the mention and the charged rate are separate kinds of evidence rather than one condition.
- Add the second limb: a positive rate the registration State's own schedule carries, resolved through the same per-Member-State registry lookup the Spanish check uses.
- Keep the Spanish-tax refusal at the top of the predicate rather than inside either limb.
- Gate both limbs, the discriminating shared-rate case, and three negative controls.

## Outcome

The concordance rung corroborates a foreign registration with a second printed signal, and that signal had exactly one source: the reverse-charge mention. Only one entry in the statutory legend vocabulary declares it expects no repercutido line, so the rung recognised one phrase and nothing else. The ordinary cross-border invoice does not print it — a supplier registered elsewhere that simply charged its own country's VAT corroborated nothing and fell to an operator question.

That was safe rather than wrong, and it was recorded as a gap rather than left to be found. It is now closed by the other thing such a document carries: the tax it charged. A rate the registration State's own schedule carries is the issuer taxing under the law it claims to be established under, stated in arithmetic rather than in a phrase, which is harder to print by accident.

The discriminating case is a rate Spain also carries. Twenty-one per cent is the general rate in Spain and in the Netherlands alike, so a Dutch-identified issuer charging it has printed something both readings explain equally and it must not corroborate. It does not — and the walk does better than merely declining, because a charged Spanish registry rate is itself a Spain-indicating signal, so the disagreement reaches the operator as a conflict naming it. The exclusion is therefore structural rather than a second rule: the walk only reaches concordance when no Spain-indicating signal fired.

Both schedules are asked of the registry rather than compared against literals, so a rate a schedule stops carrying stops corroborating, and a State whose rate changes moves with it.

## Verification

The gap measured at HEAD before the change, through the production walk:

    German VAT no. + 19% charged, no country, no legend -> (None, None)
    German VAT no. + reverse-charge legend, no tax      -> (eu_member, concordant_registration)

After:

    DE id + 19% (German, not Spanish) -> (eu_member, concordant_registration)
    DE id + 21% (not a German rate)   -> (None, None)
    DE id + 19% but NO date           -> (None, None)
    DE id + reverse-charge legend     -> (eu_member, concordant_registration)
    DE id + nothing                   -> (None, None)
    DE id + 0%                        -> (None, None)
    NL id + 21% (shared ES/NL rate)   -> conflict: "the document charges IVA at a Spanish registry rate"

Gates:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_concordance_signals.py -n0 -q -m unit
    8 passed in 4.29s

    uv run --no-sync pytest src/cadrumo/application/ledger/tests src/cadrumo/domain/iva/tests -n0 -q -m "unit"
    5 failed, 1896 passed, 26 deselected, 16 warnings in 200.97s

Mutation proof, from a plugin outside the repository rebinding the rate limb to a constant refusal, which restores exactly the single-source rule:

    [mutation] rate-limb concordance removed (single-source rule restored)
    [mutation] patched limb invoked 6 times
    2 failed, 6 passed in 5.55s

The invocation counter is the control: a limb the walk never reached would leave the gate green for a reason unrelated to soundness, and a single-target mutation has no sibling that would expose it.

## Notes

The negative control caught my own fixture rather than the code, which is the point of having it. The first draft asserted that seven per cent is carried by no schedule and therefore corroborates nothing; seven per cent is Germany's reduced rate, so the case failed correctly against a fixture that had picked a lawful German rate while claiming nobody carried it. Both schedules were then measured across a spread of rates and the control moved to a rate neither carries. The note is kept in the test so a later reader does not repeat the assumption.

An earlier probe reported that concordance did not fire even for its own single source. That was wrong and was corrected before it reached anybody: the probe had dropped the accent from the mention, so the legend matcher declined it. Re-measured with the accented phrase, the pre-existing signal worked exactly as documented.

Five failures in the shared lane were attributed rather than assumed. Four are a pydantic validation error inside the LLM provider response model, which names no establishment surface. The fifth expects an unresolved-role finding, and the decisive check was to re-run it with the pre-widening behaviour restored: it fails identically, and the widened limb is invoked zero times, so that path never reaches this change. The file also carries no reference to the ladder.
