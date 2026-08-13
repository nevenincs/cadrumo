---
tags:
  - '#exec'
  - '#advisory-grounding'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:a7b13f2da21934eb1f258d0c76465722c92eaa6b7a51a3ae933670fa249b1a10'
step_id: 'S10'
related:
  - "[[2026-08-10-advisory-grounding-plan]]"
---

# Record the four LIRPF art. 81.1 maternidad sites in the calculate-input module (_maternidad_ceilings_unresolved_advisory, _maternidad_cotizaciones_ceiling_advisory, _maternidad_ambiguous_relacion_advisory, _maternidad_meses_withheld_advisory) as excluded from this campaign's grounding population rather than grounded or silently dropped. They hit the identical two-vintage-excerpt wall the P02.S03 hard gate already excludes four other sites over: ley-35-2006:art-81-1 has no catalogue entry of its own, only the whole-article ley-35-2006:art-81, which still cites the two-vintage excerpt awaiting an operator stamp under the legal-corpus-vintage plan. Adding a finer article-81-1 entry or repointing art-81 is a corpus-vintage decision, not an advisory-grounding one, so it is rowed against that campaign with this measurement attached rather than smuggled into this sweep. Re-open these four sites once that repoint lands

## Scope

- `src/cadrumo/application/modelo/_calculate_input.py`

## Description

- Re-confirmed, rather than assumed from the P03.S06 measurement, that `ley-35-2006:art-81-1` still has no catalogue entry of its own — only the whole-article `ley-35-2006:art-81` exists, and that entry still cites the two-vintage excerpt the P02.S03 hard gate excludes four sibling sites over (the guarderia advisory sites in the minimo-descendientes advisory module).
- No source file changed. This Step is the recording itself: the four maternidad sites (`_maternidad_ceilings_unresolved_advisory`, `_maternidad_cotizaciones_ceiling_advisory`, `_maternidad_ambiguous_relacion_advisory`, `_maternidad_meses_withheld_advisory`) stay ungrounded, on purpose, until the legal-corpus-vintage campaign's art-81 repoint lands and carries an operator stamp.

## Outcome

The P03.S06 measurement's second escalated finding is closed out with an explicit disposition rather than left implicit. Population accounting for this campaign's P03 phase: five threaded (P03.S05), fifteen confirmed properly silent (P03.S06), one rule violation remediated (P03.S07), five newly grounded via `asserted_legal_refs` (P03.S09 plus the earlier P03.S05 pair), four explicitly excluded pending a sibling campaign (this Step), and six left unmeasured and named as such (`_modelo_bindings.py`'s `issue.detail`-sourced sites, per the P03.S06 exec record).

## Notes

No incidents. No code touched. This record is deliberately the only artifact for this Step — the disposition itself, not a workaround, per the same "stop and report rather than route around it" discipline the P03.S05 row states for a dependency-direction wall. The legal-corpus-vintage plan is owned by a different agent on this campaign and was not touched.
