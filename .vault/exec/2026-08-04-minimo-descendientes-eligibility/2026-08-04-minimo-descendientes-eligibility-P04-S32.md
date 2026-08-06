---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:a22eff00f811c1792073b6d6e3754d0ffbfd1b88626cfff24db319a2b59e15fd'
step_id: 'S32'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Refuse and advise on the pre-filter declaration rather than the post-filter pairs

## Scope

- `src/cadrumo/application/modelo/_calculate_input.py`

## Description

- Key the two-authorities refusal on the pre-eligibility-filter declaration rather than on the resolved pairs, which are already filtered to months the predicate granted.
- Fire the withheld and ceilings-unresolved advisories unconditionally instead of gating them on the calculate flag being absent.

## Outcome

A profile that declares months, has every one of them withheld by the engine, and also supplies the calculate flag now refuses as two competing authorities. Before the change it produced no refusal and no advisory, and the flag won silently.

The two concerns no longer share one external gate. Refusing on conflict and disclosing a withholding are different questions, and tying both to the flag's presence meant the one branch where the operator most needed to be told their records had been rejected was the single branch in which nothing was said.

The same hole existed when a revision does not resolve the Art. 58.1 and Art. 61 ceilings, because that path also empties the resolved pairs. Keying on the declaration closes both at once.

## Notes

Committed by the implementing agent under its own commit rather than swept, and verified afterwards with a numstat check confirming exactly two files and nothing foreign.

Mutation-proofed: the condition was reverted in a tracked-file window, the new test confirmed red, the condition restored, and the test confirmed green again, with the diff verified clean before committing. No mutation window was left on a tracked file.

Neither branch had any test before this Step. The number the operator received was their own explicit flag, so it was not itself a wrong figure -- which is why this reads as a disclosure defect rather than an arithmetic one, and why it was ranked below the two over-grants.
