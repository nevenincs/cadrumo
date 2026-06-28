---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-28
modified: '2026-05-28'
step_id: S398
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-source-jurisdiction-axis-adr]]"
  - "[[2026-05-28-source-jurisdiction-axis-research]]"
---

# `cross-domain-continuity` `W04.P19.S398` (slot repurpose + research-memo hygiene)

Closes the architect-2 review cycle on the source-jurisdiction-axis W02.P03 open question and reuses the freed S398 plan-Step slot — previously occupied by the rolled-back M131 implies_nonzero predicate — to track the FU-#226 corpus-blocker. Companion research-memo frontmatter hygiene wired in the same commit.

Commit: `806326a18`

- Modified: `.vault/plan/2026-05-26-cross-domain-continuity-plan.md` (S398 row repurpose)
- Modified: `.vault/research/2026-05-28-source-jurisdiction-axis-research.md` (frontmatter related: wiring)

## Description

Two related actions landed in this commit; both flow from the architect-2 verdict on the W02.P03 predicate-vs-classifier question.

### Architect-2 W02.P03 verdict — Option A endorsed

The architect-2 review of the classifier-vs-predicate research memo (`2026-05-28-source-jurisdiction-axis-research.md` at e22dd26c7) returned the Option A endorsement. Per the verdict:

- The W02.P01 and W02.P02 Step bodies in the M210 IRNR Phase 2 engine plan stand as drafted (aggregation-time classifier with typed issues per row).
- No re-decomposition of the W02 wave is required.
- The W02.P03 Step (the open question itself) is closed by the verdict.

The c159966df rollback (M131 implies_nonzero predicate) is cited in the verdict as the load-bearing concrete instance of the predicate-route silent-refusal failure mode; the verdict reinforces the lesson captured in the S398 dual-narrative record.

### S398 slot repurpose

The S398 plan-Step ID was originally bound to "structural implies_nonzero predicate on M131" — the work that landed at 31b332ed0 and rolled back at c159966df. With the rollback complete and the predicate no longer authored on any modelo, the slot was free for re-use.

This commit reuses the freed slot via `vault plan step edit` to track FU-#226: the Orden EHA/672/2007 module-tarifa corpus authoring blocker that prevents the M131 EO calculation engine from landing. The corpus-blocker work is currently tracked as task #226 in the campaign queue and is the load-bearing dependency for the next M131 calculation pass; promoting it into a plan-Step slot makes its blocker status visible at the plan level rather than only in the task queue.

The repurpose is a `vault plan step edit` operation (description replaced; canonical S398 identifier preserved per the convention ADR's gap-no-reuse rule on Step IDs).

### Companion research-memo frontmatter hygiene

The 2026-05-28 research memo at e22dd26c7 landed body-only with `related: []` (vault-CLI scaffold default). The same commit lands the frontmatter hygiene pass wiring the related field with two wiki-links:

- `[[2026-05-27-source-jurisdiction-axis-adr]]` — the ADR whose Consequences section flags S385b as deferred; the research memo's W02.P03 decision substrate flows directly from that deferral.
- `[[2026-05-26-cross-domain-continuity-plan]]` — the epic plan that owns the source-jurisdiction-axis decomposition and the deferred-work tracking.

Pattern parity with the S386b hygiene record (27770c166) on the source-jurisdiction-axis ADR.

## Why this record exists

The S398 plan-Step ID has had three distinct lifecycles in this campaign:

1. **Original binding** to "structural implies_nonzero predicate on M131" — landed at 31b332ed0.
2. **Rolled back** at c159966df after the architect-2 BLOCKER verdict; documented in the S398 dual-narrative record at `2026-05-28-cross-domain-continuity-W04-P19-S398.md`.
3. **Repurposed** in this commit to track FU-#226 corpus-blocker.

Without this record, a future audit reading the plan would see "S398: FU-#226 corpus-blocker tracker" without knowing the ID was previously bound to something else, and without context for the architect-2 W02.P03 verdict that authorised the repurpose. The dual-narrative record at `W04-P19-S398.md` covers lifecycles 1 + 2; this record covers lifecycle 3.

## Verification

- Plan body inspection confirms the S398 row description now reads as the FU-#226 corpus-blocker tracker rather than the implies_nonzero predicate scope.
- Research-memo frontmatter inspection confirms the related: field carries the two wiki-links.
- Both wiki-links resolve to existing documents in the vault.

## Gate evidence

- G1 no naked env reads: unchanged; vault-doc + plan-edit commit only.
- G2 typed pydantic at boundary: N/A.
- G3 user messages via tr(): N/A.
- G4 no locale yml hand-edits: unchanged.
- G5 no shims: plan-Step edit via the `vault plan step edit` CLI surface; no manual structural edits.
- G6 no tautological tests: no tests touched.

## References

- Source-jurisdiction-axis ADR: the W02.P03 deferred-work question this verdict answers.
- Research memo at `2026-05-28-source-jurisdiction-axis-research.md` (e22dd26c7): the architect-2 verdict substrate.
- S398 dual-narrative record at `2026-05-28-cross-domain-continuity-W04-P19-S398.md`: lifecycles 1 + 2 of the same Step ID.
- S386b hygiene record at `2026-05-28-cross-domain-continuity-W12-P65-S386b-hygiene.md`: pattern parity for the companion frontmatter hygiene.
- FU-#226: the Orden EHA/672/2007 corpus authoring blocker now tracked at the plan-Step level.
- M210 IRNR Phase 2 plan: W02.P01 and W02.P02 stand authoritative per the Option A verdict; W02.P03 closed by the verdict.
