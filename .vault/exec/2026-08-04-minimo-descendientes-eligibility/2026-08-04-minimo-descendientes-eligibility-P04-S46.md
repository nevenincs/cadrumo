---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:c7564c86f82a6e49355a3b4f21bfb6a24cd04875fbf74f746182959f961f4c25'
step_id: 'S46'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Cut two over-cap advisories under the diagnostic message limit

## Scope

- `src/cadrumo/application/modelo/_minimo_descendientes_advisory.py`

## Description

- Cut the Art. 58.2 entry-date advisory, whose static prose exceeded the cap before any substitution.
- Cut the guardería spend-shape advisory, which crossed the cap at three affected descendants.
- Preserve in both what is withheld, the statutory ground, and the routes an operator can declare.

## Outcome

Both advisories can now be constructed at every household size, with real headroom rather than a margin.

The entry-date advisory had a static floor of 528 characters against a 512 cap — verified by walking the syntax tree and summing literal text only, every substitution counted as zero. **It could not be constructed for any input at all.** A single adopted descendant with no entry date recorded exited the calculate verb with a failure code, and the operator saw a generic instruction to check arguments that were correct while the real cause reached only the error log.

Worse, the domain layer documents the opposite contract: it permits an entitling relación with no entry date expressly because the calculate path raises a visible advisory for exactly that state. The state was deliberately allowed on the promise of an advisory that could not exist.

Floors are now 374 and 377, worst-case rendered 476 and 482.

## Notes

The first cut was not enough, and measuring at a single index would have shipped it. After trimming, the entry-date advisory still exceeded the cap **by one character** at extreme counts, because the bounded name list grows as the digits of its "and N more" clause grow. The interaction between a bounded variable term and a trimmed fixed term is not visible from either one alone — which is the same failure that produced the defect, one level up.

The class had been misdiagnosed, including by the coordinator. The earlier crash in a sibling module was framed as an unbounded list biting at thirteen descendants and therefore rare. The real defect is **fixed prose measured against nothing**, and it bites at one. The bound introduced earlier works and was necessary; it was not sufficient, because nobody measured the constant floor — and the module that invented that bound carried both of these advisories.

The enumeration is not the fix and is tracked separately: sixty hand-written messages against a silent cap will drift again on the next copy edit.

One failure was attributed rather than absorbed: a derived-binding count assertion read one higher than expected, caused by an in-flight binding for the guardería increment landing in a parallel piece. Stale-count shape, belonging with that piece.
