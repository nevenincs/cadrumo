---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:4ca135e1d83f44c44285416ff500124c0c3311bec484496133a813a905207607'
step_id: 'S06'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-08-05-ci-lane-deconflation-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Close the entrypoints CLI integration failures, measured at 18 across 8 modules with 138 passing, and regenerate the set from two intersected runs rather than one and ## Scope

- `src/cadrumo/entrypoints/cli/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Close the entrypoints CLI integration failures, measured at 18 across 8 modules with 138 passing, and regenerate the set from two intersected runs rather than one

## Scope

- `src/cadrumo/entrypoints/cli/tests`

## Description

- Re-measure the entrypoints integration lane across intersected runs rather than one pass.
- Run the serial selection separately so the module set is actually covered.
- Measure committed state as well as working-tree state.

## Outcome

Closed on an empty three-way intersection, a full serial pass, and a committed-state
measurement. The row asked for two intersected runs; three were taken.

**Parallel, identical selection across all three:**

    uv run --no-sync pytest -q -n 8 -m "integration and not serial and not os_keychain" \
      --tb=line --no-header src/cadrumo/entrypoints/

    run 1 @ 71c999aeb7   29 failed, 3334 passed, 9 warnings in 338.17s
    run 2 @ 71c999aeb7        3363 passed, 9 warnings in 537.72s
    run 3 @ 36cab77343        3363 passed, 9 warnings in 578.77s
    3-way intersection: EMPTY

**Serial, quoted separately because folding it into a total is what hid the gap twice:**

    uv run --no-sync pytest -q -m "integration and serial and not perf and not os_keychain" \
      -n0 --tb=line --no-header src/cadrumo/entrypoints/

    @ 8986d07d7a   52 passed, 4248 deselected in 301.77s

All 52 ran, including the `test_lazy_command_tree.py` cold-start budget pair that xdist held
out of every earlier measurement of this lane.

**Committed state, which no earlier reading of this lane had:** extracted HEAD `36cab77343`
via `git archive`, guard confirming `cadrumo` resolved inside the extraction on both runs —
3337 passed, 26 failed, intersection identical, all 26 classified as instrument artefacts (25
subprocess the installed console script, 1 needs gitignored `docs/cli/index.rst`). Zero HEAD
defects.

## Verification

The invocations above are quoted rather than summarised, with their selections stated, per
this plan's own `P04.S26`. The serial line is quoted separately for the reason that row
exists: a parallel total does not cover a module set when xdist holds serial tests out, and a
record reading "the lane passes" would have concealed exactly the two tests that reopened this
row.

**The 29 failures in run 1 were diagnosed rather than discarded.** All one cause — `category
profile registry missing categories: ['suministros_local_afecto']` — from a peer mid-landing a
spending category. Confirmed by token presence: absent from both `_spending_category.py` and
`profiles/2024.toml` at HEAD, present in both in the working tree. Run 1 caught the interval
where one side had landed and the other had not.

That is the correct disposition for a transient: not "ignore the red", but establish which
tree it describes. A count discarded without that check is indistinguishable from a count that
was hiding a defect.

## Notes

**This row was reopened twice, and both times for the same structural reason: a total that did
not cover its module set.** The first measurement moved 19 to 28 on peer churn, which the
plan's Verification section already required intersecting to defeat. The second reported a
passing count while xdist silently held the cold-start pair out — a partial selection reading
as a complete one. The serial invocation being quoted separately in this record is the direct
remedy for the second, and it is why the row can be closed now rather than re-measured a
fourth time.

**A count row is the hardest kind to close honestly**, because the deliverable is a number and
a number can be produced by an instrument that answered a narrower question. Every earlier
attempt on this row produced a true number about the wrong population. The evidence that
finally closes it is not a better number but three measurements whose selections are stated
and whose disagreements are explained.

**Two independent classifications reached the same partition on the committed-state run.** The
executor classified by reading what each failing test wanted; the reviewer confirmed those
wants are gitignored or untracked at HEAD, so their absence from an archive extraction is
systematic. Agreement between a semantic reading and a mechanical check is worth more than
either alone, because they fail in different directions.
