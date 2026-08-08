---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:5fa3ea1d7af07ab339fc201466aa4bee134c2b86f1736936bc81de7ec2991bf9'
step_id: 'S07'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Re-key the per-sheet page-length inventory on the design file rather than the parsed year

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`

## Description

- Replace the year-keyed inventory this signal read with the publication-ordered claimed-design sequence.
- Feed all three signals from one walk rather than three independently built maps.
- Add the verdict-level assertion that a mid-course boundary reaches the failure text, gated on the property.
- Prove it bites by restoring year-keying from outside the repository.

## Outcome

The page-length signal now reads each design's own per-sheet totals from the claimed-design sequence rather than from a year-keyed map of length tuples. This is the only signal that sees growth landing in unnumbered fields - Modelo 303's sheet DP30302 going from 1706 to 1900 positions is invisible to the box key - so a year whose second design was discarded lost this signal entirely for its mid-year boundary. The record-set decomposition check that shares this data was re-keyed with it, since it compared the same two year-keyed entries and would otherwise have kept reading a map the rest of the loop no longer used.

**Landed as one coherent change with the other two re-keying Steps, deliberately.** All three per-signal inventories fed one boundary-derivation loop, so re-keying any one alone would leave that loop pairing design files for one signal and parsed years for the others - evidence for the same boundary landing under two different keys that never meet. This module produces one verdict, so a half-re-keyed state is not a smaller version of the fix, it is an incoherent instrument. One commit, three Step Records, each naming its own signal.

**Three walks became one.** Each signal previously rebuilt its own inventory, which is how they came to disagree about which designs existed: a design readable by one signal and not another entered one map and not the others. The boundary derivation now walks the claimed designs once, in publication order, and feeds all three signals from that single sequence.

**The assertion that makes this provable** states that the verdict must contain at least one boundary whose two years are EQUAL, which is what a mid-course split looks like once both halves are visible. It pins no year, no modelo and no count, so it survives AEAT splitting a different ejercicio and cannot be satisfied by a stale constant. It also guards the other side, confirming the corpus actually holds a mid-split inside a gated span, so a corpus that lost one fails loudly rather than passing by having nothing to find.

**The remaining gap is measured and attributed, not left as a round number.** The verdict now names 19 of the 22 boundaries the independent union found inside gated spans, closing 4 of the 7. All three that remain are Modelo 390 and each has a named cause:

- **2018/2019** - 0 boxes moved, 0 added, 0 removed, page lengths identical, 0 occupancy transitions. Only the description-keyed pass sees it, via a Regimen Simplificado slot changing from a Lorca-specific reduction to a generic one at a fixed offset and width. That pass is a separate open row.
- **2015/2016** - 0 moved but **6 boxes ADDED**; page lengths abstain because the 2015 design is a flattened PDF parse; 0 occupancy.
- **2016/2017** - 0 moved but **20 boxes REMOVED**; page lengths identical; 0 occupancy.

The last two expose a signal gap no open row covered: the box comparison reports only boxes that MOVED and reads nothing about set MEMBERSHIP, so a box added or removed with no displacement is invisible to every signal this module has. Opened as its own row. The blindness is masked at 2017/2018, where 72 removals coincide with movement the gate does see, which is why it survived this long.

## Verification

    uv run --no-sync pytest <this module> -p no:randomly -n0 -q
    1 failed, 9 passed in 156.37s

The verdict moved exactly where the design-file keying predicts and nowhere else:

    modelo 200 '2024-y-siguientes'   1 re-layout  (was 1, unchanged)
    modelo 303 '2009-y-siguientes'   8 re-layouts (was 5)
    modelo 303 '2023-y-siguientes'   4 re-layouts (was 3)
    modelo 390 '2010-y-siguientes'   6 re-layouts (was 6, unchanged)

Modelo 303 now names a mid-year boundary in 2018, 2021 and 2024, three boundaries no signal could previously report, and its counts match the independently re-derived union exactly at 8 and 4. Modelo 200 and Modelo 390 are unchanged because neither carries a genuine mid-split ejercicio.

Mutation proof, from **outside** the repository, restoring the defect. A plugin on the interpreter path rebinds the claimed-design walk to keep one design per year via a setdefault over a filename sort:

    PYTHONPATH=<scratch>/mut uv run --no-sync pytest <this module> -p year_keyed -p no:randomly -n0 -q -rA
    MUTATION APPLIED: inventory rebound to one-design-per-year, holder confirmed, modelo 303 claimed designs 9 -> 7
    FAILED ...::test_the_verdict_names_a_mid_course_boundary_where_aeat_split_an_ejercicio
    AssertionError: the corpus holds a mid-course split inside a gated span (ejercicios 2018, 2021
    and 2024) but the verdict names no boundary inside a single ejercicio, so an inventory is back
    to keeping one design per year and its silence about that boundary means nothing

Under the mutation Modelo 303 falls back to 5 and 3 re-layouts - the exact pre-fix figures - confirming the mutation restores the original defect rather than breaking something else. The plugin refuses rather than passing when no gated revision claims two designs for one ejercicio, when the rebinding does not take, and when year-keying drops no design.

    uv run --no-sync ruff format --check <this module>   All checks passed
    uv run --no-sync ruff check <this module>            All checks passed!
    uv run --no-sync ty check <this module>              All checks passed!

## Notes

**A correction to the assertion, made before it shipped.** The first version derived BOTH sides - whether a mid-split exists, and whether the verdict names one - from the same span helper. Under mutation it therefore reddened on its own vacuity guard, reporting that no gated revision claims an ejercicio carrying two designs, rather than on the assertion that matters; that proves only that the function changed. The availability side now comes from the raw publication-order enumeration, so the mutation leaves the guard satisfied and the real assertion is the one that fires. This is the same defect corrected in the ordering Step, and it recurred because deriving two sides of a test from one helper reads as economy.

**A dedup defect in the ordering primitive, found and fixed here.** That primitive deduplicated designs by raw bytes, which is the obvious identity and the wrong one: AEAT bundles the same design twice in two container formats, and an xls and an xlsx of one document are different bytes. Measured, Modelo 200 carries such a twin for EVERY ejercicio from 2015 to 2025, so byte-keying reported all eleven of those years as carrying two designs - eleven mid-course splits on a modelo that has none. Identity is now the parsed declaration, which collapses the twins while leaving Modelo 303's three genuine pairs standing. Byte-keying looked correct because it does collapse the corpus's OTHER duplicate shape, the same file bundled twice under a truncated filename.

**Scope held.** The year-shaped helpers that answer which YEARS are unmeasured are untouched, because that question is genuinely year-shaped and the coverage guard reporting it is not a comparison. Only the comparison was re-keyed.

**Not measured.** Whether the description-keyed pass or a membership signal would find further boundaries beyond the three named above is not known, because neither has landed. The 19-of-22 figure is against one independent re-derivation, and that re-derivation excluded Modelo 390's 2004 to 2014 designs, which are bundled only as xsd, fall outside the parsers' accepted suffixes and were never read.
