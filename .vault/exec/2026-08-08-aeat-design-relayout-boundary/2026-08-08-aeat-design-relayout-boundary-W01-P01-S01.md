---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:2b7f201f54aa885df71d55d2f59d3867132775d6dbe359013283308422bc1865'
step_id: 'S01'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Re-derive the full boundary set as the UNION of four passes over the bundled designs

## Scope

- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/`

## Description

- Enumerate every readable bundled design per modelo, keyed on the FILE and deduplicated by CONTENT, ordered chronologically rather than by filename.
- Run four passes over each adjacent pair: box-number-keyed movement, per-sheet total-positions and record-set decomposition, slot occupancy in both directions, and a description-keyed pass over unnumbered slots at a fixed position and width.
- Take the union per modelo, then restrict it to each gated revision's claimed span so the count is comparable against the shipped gate's verdict.
- Classify every boundary on the separate authoring-scope axis, never merged with whether it is real.

## Outcome

**The union is 22 boundaries inside the four gated revision spans, against the 15 the gate reports today. It exceeds the gate by 7.** The earlier lower bound of one extra boundary on Modelo 303 was a floor, as stated, and the true figure is seven times that.

Per revision, with the pass that found each boundary. `P1` is box-number movement, `P2` page length and record set, `P3` occupancy, `P4` the description-keyed unnumbered pass.

**Modelo 200 `2024-y-siguientes` - union 1, gate 1, no gap.**

    2024/2025        P2,P3,P4    SPLIT

**Modelo 303 `2009-y-siguientes` - union 8, gate 5, gap of 3.**

    2014/2015        P2,P3,P4    out
    2016/2017        P1,P2,P4    out
    2017/2018        P1,P3,P4    out
    2018 mid-year    P1,P3,P4    out
    2018/2019        P1,P3,P4    out
    2020/2021        P1,P2,P3,P4 out
    2021 mid-year    P1,P3,P4    out
    2021/2022        P1,P2,P3    EDGE

**Modelo 303 `2023-y-siguientes` - union 4, gate 3, gap of 1.**

    2023/2024        P3,P4       SPLIT
    2024 mid-year    P1,P3,P4    SPLIT
    2024/2025        P2,P3       SPLIT
    2025/2026        P1,P2,P3    SPLIT

**Modelo 390 `2010-y-siguientes` - union 9, gate 6, gap of 3.**

    2015/2016        P1          out
    2016/2017        P1,P4       out
    2017/2018        P1,P2,P3,P4 out
    2018/2019        P4          out   <-- found by P4 ALONE
    2020/2021        P1,P2,P3,P4 out
    2021/2022        P1,P2,P3,P4 EDGE
    2022/2023        P1,P2,P3    SPLIT
    2023/2024        P1,P2,P3,P4 SPLIT
    2024/2025        P3          SPLIT

**Authoring scope is unchanged, and that is the load-bearing separation.** Every one of the seven boundaries the gate misses is out-of-window. Splitting the two axes gives, per modelo: Modelo 303 one edge revision at 2022 plus four in-window splits, so **6 revisions**; Modelo 390 three splits plus one edge, so **4 revisions**; Modelo 200 one split, so **2 revisions**. That is exactly what the plan encodes after the earlier reconciliation, so **no authoring row was added, removed or re-pointed by this Step**. A boundary being real does not put it in authoring scope, and the union growing by seven changes what the instrument must be able to see without changing what must be authored.

**The fourth pass earns its place, and it over-reports.** Across the whole bundled corpus it is the sole finder of three boundaries, and judged individually two are real and one is a false positive:

- **Modelo 390 2018/2019 - REAL.** Sheet 5 offsets 223 and 543, both 17 bytes wide and unmoved, go from `Reg. Simplificado - Actividad 1 - Lorca` to `Actividad 1 - Reducciones (nota 2)`. A specific earthquake-relief reduction slot was repurposed to a generic one at identical position and width. Independently corroborated by the gate's own recorded occupancy example, which names those same offsets 223 and 543 retiring at the 2024/2025 boundary - the same slot family has changed meaning at fixed offsets more than once.
- **Modelo 131 2025/2026 - REAL.** `Deducción por rentas obtenidas en Ceuta, Melilla o La Palma` becomes `Deducción por rentas obtenidas en Ceuta o Melilla` in a one-byte slot at an unchanged offset. La Palma left the deduction's scope while the flag stayed put.
- **Modelo 111 2018/2019 - FALSE POSITIVE.** `Identificación. Ejercicio` becomes `Devengo. Ejercicio` at offset 103, width 4. The field still carries the ejercicio; only the block heading above it was relabelled.

That one-in-three false-positive rate is exactly what the sub-year decision record warned of when it said a description-keyed diff cannot separate a rename from a semantic flip. The pass is necessary and its hits are not self-certifying: each must be read, and the instrument prints both texts rather than a count for that reason. Reserved transitions are excluded from this pass so it does not double-count pass three's findings.

**The lead this Step was handed resolved to nothing on its own.** Sheet `DP30303` offset 406 was reported as a revival carrying rectificativa text, and it is a pass-three occupancy finding rather than a pass-four flip: the slot is reserved on one side, so the description-keyed pass deliberately skips it. The complementaria-to-rectificativa change on Modelo 303 is therefore visible as an occupancy transition, not as a same-position re-description. The genuine pass-four flip class lives on Modelo 390 and Modelo 131 instead.

**Breadth swept beyond the gated revisions**, since the prescripción window filters what is authored rather than what is measured. Across all eleven exporting modelos with two or more readable designs the union is 60 boundaries: Modelo 100 five, Modelo 111 one, Modelo 115 one, Modelo 123 two, Modelo 130 three, Modelo 131 six, Modelo 200 fifteen, Modelo 202 five, Modelo 232 zero, Modelo 303 thirteen, Modelo 390 nine. Modelo 232 measuring zero is a real negative, not a blind one: both its designs parse and agree on every pass.

## Verification

    uv run --no-sync python <scratch>/probe_union.py          # per modelo, all bundled designs
    uv run --no-sync python <scratch>/probe_union_summary.py  # restricted to gated revision spans
    UNION across every gated revision's claimed span: 22 boundaries
      of which found by P4 alone: 1

    uv run --no-sync pytest <the span gate module> -p no:randomly -n0 -q -rA
    modelo 200 revision '2024-y-siguientes' spans 1 re-layout(s) and needs 2 revisions
    modelo 303 revision '2009-y-siguientes' spans 5 re-layout(s) and needs 6 revisions
    modelo 303 revision '2023-y-siguientes' spans 3 re-layout(s) and needs 4 revisions
    modelo 390 revision '2010-y-siguientes' spans 6 re-layout(s) and needs 7 revisions

15 against 22, so the seven-boundary gap is measured against the gate's live verdict rather than against a document's snapshot of it. The probe reads designs through the shipped parsers and reuses the gate's own source-enumeration, year-attribution and claimed-years helpers, so a divergence is a difference in method rather than in corpus.

**An ordering defect found and fixed mid-measurement, and it changed the answer.** AEAT numbers its design filenames newest-first - `01` is the 2026 design, `06` is 2025 - so a filename sort is not chronological and paired the LATE half of a mid-split ejercicio before its EARLY half. Under the wrong order, Modelo 303's eight added boxes attached to the `2023/2024` label and the mid-2024 boundary showed only occupancy; corrected, the eight boxes attach to `2024 mid-year` where they belong and `2023/2024` reports occupancy and description only. The boundary COUNT was unaffected, which is precisely why the defect could have shipped unnoticed: three adjacent designs yield two boundaries in any order. The published wording, `hasta-periodos` against `a-partir-de-periodos`, is the only chronological signal inside one year. Row `W01.P02.S68` carries this constraint onto the re-keying work.

## Notes

**A correction to this executor's own earlier report.** The prescripción floor for Modelo 200 is **2022, not 2024**. Ley 27/2014 art. 124.1 is bundled and sets the deadline at the 25 natural days following the 6 months after the period closes, so ejercicio 2021 prescribed on 2026-07-25, fourteen days before this measurement, and 2022 remains open until 2027-07-25. The earlier figure of 2024 came from reading the registry's declared deadline windows, which exist only from 2024 for this modelo - the exact absence-is-not-an-answer error this executor had flagged for Modelo 303 and Modelo 390 and then committed for Modelo 200. It went unnoticed because the modelo's revision also claims 2024 onward, so the two numbers coincided.

That correction does **not** widen this campaign. Modelo 200 filing years 2022 and 2023 are not mis-written; no revision claims them, so they already refuse. That is a coverage gap, not a wrong-offset defect, and the standing goal is that no filing year is written at wrong offsets rather than that every reachable year is served. Recorded as `W05.P11.S70` rather than absorbed silently.

**Low-confidence pairs, reported rather than folded in.** Where one side of a pair is a flattened PDF parse the page-length signal abstains and the box and description passes compare a single synthetic sheet against real ones. Those pairs are marked in the per-modelo output and cluster in the older Modelo 100, 115, 123, 130, 131 and 200 designs. None of them falls inside a gated revision's in-window span, so no authoring decision rests on one.

**Not measured, stated rather than inferred.** Whether the shipped gate's count closes the seven-boundary gap once the three inventories are re-keyed on the design file is unmeasured, because that re-keying has not landed; `W01.P02.S69` requires the reconciliation rather than assuming it. The `.xsd` designs Modelo 390 bundles for 2004 through 2014 are outside the parsers' accepted suffixes and were not read at all, so Modelo 390's pre-2015 years are unmeasured rather than clean. No gate was edited by this Step.
