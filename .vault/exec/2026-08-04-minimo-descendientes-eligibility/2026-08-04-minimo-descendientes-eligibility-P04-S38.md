---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:d9bea3bac0c207c9d555d43dafc957e693795b96936ef43eaedce6a29a24538c'
step_id: 'S38'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Advise or confirm at the point working months are declared that the child is a hijo rather than a grandchild or a minor under judicial guarda, because the ordinary predicate never reads relacion so both populations compute correctly for Art. 58.1 and 58.2 while only Art. 81.1 over-grants, and the over-grant additionally requires declared months, so that narrow conjunction reaches every already-stored record which no new enum member can do

## Scope

- `src/cadrumo/application/modelo/_calculate_input.py`
- `src/cadrumo/entrypoints/cli/_config/_descendiente.py`
- `src/cadrumo/locales/`

## Description

- Add a calculate-time advisory: when a contributing Art. 81.1 descendant (positive months, present in the resolved `pairs`) carries the unstated default relación, disclose that the stored fact cannot rule out the two Art. 58.1-eligible, Art. 81.1-excluded populations the relación axis has no member for (a grandchild/other-consanguinidad descendant, or a minor under judicial guarda y custodia).
- Add the same disclosure at declaration time, so an operator adding a descendant through `descendiente add` sees it immediately rather than only on the next calculate.
- Resolve the contributing descendant's relación by reusing the canonical fact-index reconstruction already used everywhere else, rather than adding a new field to the maternidad resolution record; reuse the same reconstruction at the declaration-time surface.
- Gate both checks on the identical narrow conjunction: contributing months positive AND relación is the unstated default. An explicit relación (adoptado, tutela, acogimiento) never fires the advisory, whether or not it entitles; a non-contributing descendant under the default relación never fires it either.
- Retire the calculate-time `--meses-trabajo-con-hijo-menor-3` flag in a prior Step in this same sequence, collapsing casilla 0611 onto the profile declaration as its one authority.
- Write ten integration tests exercising both surfaces (fires under the default relación, does not fire under an explicit relación, does not fire for a withheld or non-contributing descendant, names exactly the newly-affected indices) and run two in-process mutation proofs confirming each relación check is load-bearing.
- Trace the interaction with the pre-2023 cotizaciones-ceiling withholding (landed in a concurrent Step) and add a regression proving the two advisories cannot both threaten the same filing: a pre-2023 filing year withholds the deducción entirely before the relación question is ever asked, because the resolved contributing set is empty for those years by construction.

## Outcome

Both surfaces ship as a non-blocking `Notice` / `CalculationSourceDiagnostic` advisory, never a blocking confirmation. This follows the codebase's existing precedent for an identically-shaped problem: an unmodelled eligibility condition where the majority case is legitimate (the DT 12ª antiquity condition resolves the same way, under the same no-silent-under-declaration discipline). A blocking gate would tax every ordinary hijo declaration with an extra confirmation step for a minority-case ambiguity this application cannot itself resolve; disclosure lets the operator correct the record when it is wrong and costs nothing when it is right.

The advisory-versus-confirmation choice initially carried a "a human might not read a passive notice" counter-argument. That argument does not apply here: the `Notice` / `CalculationSourceDiagnostic` channel is the sole sanctioned diagnostic surface for this CLI, explicitly built for an LLM operator to parse the envelope programmatically, and this advisory rides the exact same channel as every other maternidad advisory (withheld months, ceilings-unresolved, the cotizaciones ceiling) the operator already consumes. It is structurally no more missable than any of those, so the "passive notice" framing imports a human-UX intuition into a channel that is not human-consumed, and the advisory framing stands on the in-tree precedent plus the blocking-cost argument alone.

The pre-2023 interaction is moot by construction, not by an added condition: the resolved contributing-months set is unconditionally empty for any filing year predating the cotizaciones-ceiling retirement, so the relación question is never reached for those years regardless of the stored relación. A direct regression proves the composed claim end to end rather than relying on that reasoning alone.

## Notes

No incidents, no data loss. While validating the pre-2023 interaction, encountered a live, uncommitted, in-progress edit by a concurrent agent to the user-profile schema TOML that intermittently exceeded a field description's length cap and flapped the whole registry load; not touched, reported, and waited for it to clear before finishing verification.
