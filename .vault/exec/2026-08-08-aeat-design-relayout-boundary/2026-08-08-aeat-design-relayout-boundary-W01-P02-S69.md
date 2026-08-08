---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:0de7c504e34f7c4f0bb1c1cc22502998434aa1c29f4ded507dbcd21e40d84dab'
step_id: 'S69'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Reconcile the hardened gate's verdict against the re-derived boundary union

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`

## Description

- Re-derive the boundary set at run time against a named HEAD rather than inheriting a figure from any record.
- Decompose every boundary by the signals that name it.
- Separate the confirmed subset from the boundaries resting on the least precise instrument.
- State what the corpus-wide figures exclude, in the same breath as the figures.

## Outcome

**Measured against HEAD `a527f30cb9dff8c71621a0bc1a168b4c39b3491f`**, with the module byte-identical to that commit. Naming the tree is not ceremony: two agents disagreed for twenty minutes today about whether the registry was broken, purely because one read a working copy and the other read the blob, so a reconciliation that does not name its subject is a measurement of nothing in particular.

**The verdict names 22 boundaries and the shortfall is zero.** Every boundary the four-pass derivation finds inside the four gated revision spans is reported by the gate.

**That agreement is NOT corroboration, and reporting it as such would repeat this campaign's most expensive error.** The union derivation began as an independent instrument. It is no longer one: after the design-file re-keying and the box-marker consolidation it shares the gate's parsers, its design enumeration, its publication ordering and its marker. Two instruments that share an implementation agree by construction. This is exactly the shape that produced "Modelo 200 - union 1, gate 1, no gap" earlier in this campaign, where both sides carried a four-digit marker against a five-digit modelo and their agreement was worth nothing. The convergence was found while everything agreed rather than when something failed, which is the only reason it is recorded here rather than discovered later.

So the substance of this row is not the 22. It is the **decomposition**, which survives the loss of independence because it says which signal saw what rather than offering a second opinion.

### Every boundary and the signals naming it

    revision                boundary        scope   signals
    m200 2024-y-siguientes  2024/2025       SPLIT   movement, membership, record-set, occupancy x2, description
    m303 2009-y-siguientes  2014/2015       out     page-length, occupancy-revive, description
    m303 2009-y-siguientes  2016/2017       out     movement, membership, record-set, description
    m303 2009-y-siguientes  2017/2018       out     membership, occupancy-revive, description
    m303 2009-y-siguientes  2018 mid-year   out     membership, occupancy-retire, description
    m303 2009-y-siguientes  2018/2019       out     membership, occupancy-revive, description
    m303 2009-y-siguientes  2020/2021       out     movement, membership, record-set, occupancy-retire, description
    m303 2009-y-siguientes  2021 mid-year   out     membership, occupancy-revive
    m303 2009-y-siguientes  2021/2022       EDGE    movement, membership, page-length, occupancy x2
    m303 2023-y-siguientes  2023/2024       SPLIT   occupancy-retire, description
    m303 2023-y-siguientes  2024 mid-year   SPLIT   membership, occupancy-revive
    m303 2023-y-siguientes  2024/2025       SPLIT   page-length, occupancy-retire, occupancy-revive
    m303 2023-y-siguientes  2025/2026       SPLIT   movement, membership, page-length, occupancy-revive
    m390 2010-y-siguientes  2015/2016       out     membership
    m390 2010-y-siguientes  2016/2017       out     membership, description
    m390 2010-y-siguientes  2017/2018       out     movement, membership, page-length, occupancy x2, description
    m390 2010-y-siguientes  2018/2019       out     description
    m390 2010-y-siguientes  2020/2021       out     movement, membership, page-length, occupancy-revive, description
    m390 2010-y-siguientes  2021/2022       EDGE    movement, membership, page-length, occupancy-revive, description
    m390 2010-y-siguientes  2022/2023       SPLIT   movement, membership, page-length, occupancy-revive
    m390 2010-y-siguientes  2023/2024       SPLIT   movement, membership, record-set, occupancy-revive, description
    m390 2010-y-siguientes  2024/2025       SPLIT   occupancy-retire

### Confirmed, separated from reviewed-but-rejected

**Confirmed: 21 of 22.** Each is named either by two or more signals, or by a signal other than the description-keyed pass. The description pass contributes evidence to 14 boundaries; on 13 of those it is corroborating rather than deciding, and a false positive there adds noise to the evidence rather than a wrong split.

**Resting solely on the description-keyed pass: 1.** Modelo 390 `2018/2019`, marked `DESCRIPTION-KEYED PASS ONLY` in the verdict text. That pass runs roughly one false positive in three on individual verdicts, so this boundary is offered for judgement rather than as a fact. It was reviewed by hand and accepted: a Regimen Simplificado slot on sheet 5 goes from a Lorca-specific reduction to a generic one at an unchanged 17-byte position, and the same sheet-5 offsets 223 and 543 are independently reported by the occupancy signal retiring at a later boundary. It is out-of-window, so no authoring row depends on it.

**Reviewed and rejected: the false positive that survives in the corpus is Modelo 303 `2014/2015`**, where the pass reports a leaf going from `regimen simplificado` to `Regimen Simplificado (RS)` - a rewording with an added parenthetical, not a meaning change. It is rejected as description evidence and costs nothing, because page-length and occupancy already name that boundary independently.

**The finding the split executors need most.** Three boundaries rest on a SINGLE signal, and one of them is **in authoring scope**:

- `m390 2015/2016` - membership only - out-of-window.
- `m390 2018/2019` - description only - out-of-window.
- **`m390 2024/2025` - occupancy-retire only - SPLIT, in scope.** Nothing else corroborates it: no box moved, no box was added or removed, no page length changed, no description flipped. Three Regimen Simplificado slots retire into reserved space and that is the entire case. It is a real boundary on the evidence, but a split authored there rests on one instrument, and that is worth knowing before authoring rather than after.

### Modelo 200

**The count survived, the method did not.** Its boundary count was 1 before the marker consolidation and is 1 after, and that stability is a coincidence of shape rather than confirmation: the revision claims a single adjacent design pair, already named by the record-set and occupancy signals, so no change to the box comparison could have moved the count. Had it claimed a third design it would have moved. What changed is everything underneath - the gate read 23 of that modelo's boxes and now reads 3440, and the boundary is now evidenced by 1140 of 3194 shared boxes moving, 246 added and 145 removed, where previously the box signals contributed nothing at all. A reconciliation reporting "Modelo 200 unchanged" would be true and misleading.

### What the corpus-wide figures exclude

The 22 covers only the four gated revision spans. The wider per-modelo sweep across all exporting modelos found 60 boundaries, **and that figure excludes Modelo 390's 2004 to 2014 designs, which are bundled only as `.xsd`, fall outside the parsers' accepted suffixes and were never read at all** - those years are unmeasured rather than clean, and 60 must not be taken as complete. One further pair, Modelo 390 `2015/2016`, has a flattened PDF on one side, so the page-length and description signals abstain there and its single membership finding is all any instrument can say.

## Verification

    git rev-parse HEAD                  a527f30cb9dff8c71621a0bc1a168b4c39b3491f
    git status --porcelain -- <module>  (clean)

    uv run --no-sync python <scratch>/reconcile.py
    gate verdict: 22 boundaries inside the four gated revision spans
    boundaries named by the description pass ALONE: ['m390 2018/2019']
    boundaries resting on a SINGLE signal: 3

The reconciliation reads the gate's own boundary structure rather than re-implementing the comparison, deliberately, because a re-implementation would now be a copy rather than a control and would present as agreement. The decomposition is derived from the evidence strings the verdict itself emits.

## Notes

**The row's premise about a shortfall no longer applies.** It was written when the gate reported 15 of 22 and required any shortfall to be named as a blind spot rather than treated as green. The shortfall is zero, closed across four Steps: design-file re-keying recovered the three mid-course boundaries, the membership signal recovered two, the description pass recovered one, and the marker consolidation recovered none but re-evidenced Modelo 200 entirely.

**Zero shortfall is not zero blindness.** It means every boundary the current four passes find is reported. A fifth class nobody has thought of would be invisible to both sides equally, and now more so than before, since the two sides share an implementation.

**Not measured.** The `.xsd` designs remain unread. The flattened-PDF pair remains partially unmeasured. The ten slots the description pass refuses to judge are printed for review and are not counted as boundaries, by design.
