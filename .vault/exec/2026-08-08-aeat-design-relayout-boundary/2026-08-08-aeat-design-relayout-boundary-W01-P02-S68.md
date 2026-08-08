---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:49aebacada815a9692c56aaf928782c65eee563e00e56b8ca9e5782ee554c0f1'
step_id: 'S68'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Order the design inventories chronologically rather than by filename

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`

## Description

- Probe whether the design file BODY asserts the periods it governs, before falling back to anything derived from the filename.
- Inspect the wording every mid-split ejercicio actually carries, rather than assuming one convention.
- Add a coverage-start reader and a publication-order inventory, deduplicated by content, that reports an unorderable year instead of guessing.
- Add an ordering-property assertion and an evidence-attribution assertion that consumes the ordered sequence.
- Prove the attribution assertion bites by restoring the defect from outside the repository.

## Outcome

**The design body asserts nothing about its own coverage, and that had to be measured rather than assumed.** Across Modelo 303's two 2024 halves the workbooks declare the identical seven-sheet set and the identical `Ejercicio de devengo (EEEE)` and `Período. (PP)` header fields, because those are slots the FILER completes, not metadata about which periods the design governs. A scan for any coverage assertion in every description, validation and content column of both files returns **zero**. So there is no in-body signal to order on, and saying so plainly is the honest answer rather than reaching for the filename while calling it chronological.

What does exist is AEAT's own published designation, which states the period bound directly: `hasta-periodos-08-y-2t` against `a-partir-de-periodos-09-y-3t`. That is a period assertion transported in the filename, and it is categorically different from the numeric listing prefix. The ordering therefore reads the declared coverage START - `hasta` runs from the year's beginning so its coverage starts at 01, while `desde` and `a-partir-de` start at the period they name - and sorts on that.

**The numeric prefix is not merely arbitrary, it is close to reversed.** AEAT numbers its published listing NEWEST first: Modelo 303's `01` is the 2026 design and its `06` is 2025. Nothing in the new ordering consults it, so a change to AEAT's listing convention cannot move the result, and no year-to-prefix table exists to go stale.

**One of the three mid-split years cannot be ordered from what AEAT declares, and it is reported rather than guessed.** Measured across every Modelo 303 ejercicio carrying two content-distinct designs:

- **2021 - orderable.** `hasta-periodo-06` then `desde-periodo-07`, coverage starting 01 then 07.
- **2024 - orderable.** `hasta-periodos-08-y-2t` then `a-partir-de-periodos-09-y-3t`, coverage starting 01 then 09.
- **2018 - UNORDERABLE.** The pair is `ejercicio-2018` and `ejercicio-2018-salvo-ultimo-periodo-12m-4t`. "Except the last period" fixes no start, and the unqualified sibling asserts nothing at all. Ordering them would be inference by elimination dressed as a measurement, so the inventory returns 2018 in its unorderable set and leaves those two in a stable but explicitly unasserted order. 2018 is outside the prescripcion window, so no authoring decision rests on it, but a consumer is now told rather than misled.

**A property that looked usable was measured and rejected.** The obvious attribution assertion is that the earlier half's box set is a subset of the later half's. It holds for 2024, which adds eight boxes and removes none, and **fails for 2021**, which adds eight and **removes one**. Asserting subset would have encoded a Modelo 303 2024 coincidence as an invariant and reddened the moment anyone looked at 2021. The shipped assertion tests direction of attribution instead.

**Two assertions land, and neither pins a number.** The ordering assertion states that within any year whose designs all declare a bound, the declared coverage starts are strictly increasing and distinct, and the half AEAT bounds with `hasta` sorts first; it also requires 2018 to be reported unorderable, so the honest-refusal path cannot rot into a silent guess. The attribution assertion walks the ORDERED sequence adjacently, exactly as a boundary-deriving consumer does, and states that the 2023-to-early-2024 transition introduces **no** new numbered box while the mid-2024 transition introduces **some**. Empty against non-empty, never eight, so AEAT adding a ninth box changes nothing.

**The attribution assertion consumes the ordering rather than re-deriving it, and that was a correction made mid-implementation.** The first version rebuilt its own map from the coverage-start reader, which left it sensitive to that helper but blind to the inventory function it exists to guard: a mutation forcing filename order would have passed. Walking the ordered sequence is what makes the mutation below possible at all.

## Verification

    uv run --no-sync python <scratch>/probe_period_assertion.py
      2024-early: coverage assertions found: 0
      2024-late:  coverage assertions found: 0
      both: sheets ['DP30300','DP30301','DP30302','DP30303','DP30304','DP30305','DP303DID']

    uv run --no-sync python <scratch>/probe_midsplit.py
      ejercicio 2018: UNORDERABLE from declared period bounds
      ejercicio 2021: ORDERABLE earlier=01 later=07; earlier subset of later? False (added 8, removed 1)
      ejercicio 2024: ORDERABLE earlier=01 later=09; earlier subset of later? True  (added 8, removed 0)

    uv run --no-sync pytest <this module> -p no:randomly -n0 -q -rA
    8 passed, 1 failed
    PASSED ...::test_a_mid_split_ejercicio_orders_its_halves_by_declared_coverage_not_by_filename
    PASSED ...::test_the_added_boxes_attach_to_the_epoch_that_introduced_them
    FAILED ...::test_no_revision_spans_a_design_relayout

Mutation proof, from **outside** the repository, restoring the exact defect. A plugin on the interpreter path rebinds the inventory to group by year and then order WITHIN the year by filename, which is what shipped before this change:

    PYTHONPATH=<scratch>/mut uv run --no-sync pytest <this module> -p filename_order -p no:randomly -n0 -q -rA
    MUTATION APPLIED: inventory rebound to filename order, holder confirmed, 4 design(s) moved
        was 15-303-...-ejercicio-2021-hasta-periodo-06...   now 08-303-...-ejercicio-2021-desde-periodo-07...
        was 05-303-...-2024-hasta-periodos-08-y-2t...       now 04-303-...-2024-a-partir-de-periodos-09-y-3t...
    FAILED ...::test_a_mid_split_ejercicio_orders_its_halves_by_declared_coverage_not_by_filename
    FAILED ...::test_the_added_boxes_attach_to_the_epoch_that_introduced_them
    AssertionError: the 2023-to-early-2024 transition must introduce NO new numbered box --
    boxes ['108', '111', '165', '166', '167', '168', '169', '170'] attributed there instead,
    which is the signature of the two 2024 halves being paired in the wrong order

That failure names the eight boxes landing on the wrong boundary, which is the original finding reproduced as a red test rather than as prose. Both mid-split years swap under the mutation, so it demonstrates the defect on 2021 as well as 2024.

The plugin **refuses rather than passing** on three no-op conditions: the attribute being absent, the rebinding not taking, and - the one that matters here - filename order turning out to EQUAL declared-coverage order, in which case the mutation would change nothing and could not red anything. It also refuses if fewer than three designs enumerate, so it cannot pass over an empty inventory.

    uv run --no-sync ruff format --check <this module>   1 file already formatted
    uv run --no-sync ruff check <this module>            All checks passed!
    uv run --no-sync ty check <this module>              All checks passed!

The type checker rejected the first draft, which compared a list holding `int | None` against its own sorted form. Fixed by asserting every member of a year reported orderable actually carries a bound before comparing, which narrows the type and adds a real check that the unorderable report is itself correct, rather than silencing the diagnostic.

## Notes

**Why a count-based assertion could never have caught this.** Three consecutive designs yield two adjacent boundaries in any order, so the boundary COUNT is identical whether the 2024 halves pair early-then-late or late-then-early. Every count-shaped check over this corpus is structurally blind to the defect, which is why the shipped assertion is about which boundary carries which evidence.

**What this unblocks and what it does not.** The re-keying rows and the split authoring rows both consumed the defective order, the latter more dangerously: a split authored against the wrong attribution places the eight boxes in the wrong revision, and no offset check, length check or digest detects that. This Step makes the attribution trustworthy. It does not re-key any inventory - the three existing per-signal maps still key on the parsed year - so the mid-year boundary remains invisible to the verdict until those rows land.

**Not measured.** Whether Modelo 390's or Modelo 200's corpora contain a mid-split ejercicio at all was not checked; the ordering primitive is generic and the assertions are Modelo 303's because that is where the three known mid-course splits are. A modelo whose designs all carry one bound per year is unaffected either way. The `.xsd` designs remain unread, as recorded previously.
