---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:63bf7076666f7f9fdc5da6c464f15a2ba0a158c6d0058175874d52ef314d909d'
step_id: 'S71'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Add a box-set MEMBERSHIP signal alongside the movement signal

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`

## Description

- Add a fourth signal reporting that the box SET changed, whether or not anything moved.
- Extract it behind a named seam so a mutation can suppress it alone.
- Add the assertion that a membership-only boundary reaches the verdict, gated on the property and with its two sides derived independently.
- Prove it by restoring movement-only reading from outside the repository.

## Outcome

**Modelo 390's verdict moved from 6 re-layouts to 8**, closing two of the three boundaries the independent union had that the gate did not. The union total inside gated spans is now 21 of 22 reported, from 19.

The defect was structural rather than incidental. The displacement check iterates the boxes two designs SHARE, so a box present in one and absent in the other falls outside its loop entirely. That is not a lesser event than a shift: a box the later design declares and the earlier one does not cannot be declared at all under the earlier layout, and a box the earlier design declares and the later one drops is a value written into space the later design puts to another use. Neither is visible to a displacement check, a page-length check, an occupancy check or a digest.

The two boundaries it recovers, both Modelo 390 and both previously reported by nothing:

- **2015/2016** - zero of 345 shared boxes moved, **six boxes added**, page lengths unreadable on the 2015 side because it is a flattened PDF parse, zero occupancy transitions.
- **2016/2017** - zero of 331 shared boxes moved, **twenty boxes removed**, page lengths identical, zero occupancy transitions.

**Why the blindness survived this long is the part worth carrying forward.** It is MASKED wherever membership changes alongside movement. The 2017/2018 boundary drops seventy-two boxes, and the displacement check reports that boundary anyway on its ninety-seven moved boxes, so a reader spot-checking whether the module notices boxes disappearing picks that pair, sees a membership change duly reported, and concludes the set is compared. The signal that was actually firing was displacement; membership was along for the ride. A co-occurring signal hiding another signal's absence is the same shape as the reserved-space rationale that was never checked, and as the byte-identity that correctly handled the one duplicate shape anybody tested it against.

**Gated on the membership property, never on the numbers.** The assertion does not state six added or twenty removed; those are today's corpus, and pinning them would train the next author to bump two constants and then detect nothing. It states that a design pair whose ONLY difference is which boxes exist still produces a boundary. It also guards the other side, requiring that such a pair exists in the corpus at all, so a corpus that lost the case fails loudly rather than passing by having nothing to find.

**The two sides are derived independently, and this is the third time that mattered.** Availability is measured straight from the parsed designs - zero movement among shared boxes, differing box sets, no page-length difference, no occupancy transition - while the reported side comes from the verdict builder. Deriving both from the verdict builder is the shape that caught this module's author twice already: under mutation such a test reds on its own vacuity guard, which proves the function changed and nothing about whether the signal works. The temptation was live here too, because the natural implementation has the expected and actual box sets coming from one extraction.

**The signal is extracted behind a named seam rather than inlined**, specifically so the mutation can suppress this signal alone while every other signal keeps running. A mutation that had to break the comparison generally would prove the module can fail, not that this signal is what sees a membership change.

## Verification

    uv run --no-sync pytest <this module> -p no:randomly -n0 -q
    1 failed, 10 passed in 189.28s

    modelo 200 '2024-y-siguientes'   1 re-layout   (unchanged)
    modelo 303 '2009-y-siguientes'   8 re-layouts  (unchanged)
    modelo 303 '2023-y-siguientes'   4 re-layouts  (unchanged)
    modelo 390 '2010-y-siguientes'   8 re-layouts  (was 6)

Only Modelo 390 moves, which is what the measurement predicted: it is the only modelo whose corpus carries a membership change with no co-occurring signal.

Mutation proof, from **outside** the repository, restoring movement-only reading:

    PYTHONPATH=<scratch>/mut uv run --no-sync pytest <this module> -p movement_only -p no:randomly -n0 -q -rA
    MUTATION APPLIED: box-SET evidence suppressed, holder confirmed, movement-only reading restored
    FAILED ...::test_a_box_added_or_removed_without_movement_reaches_the_verdict
    AssertionError: modelo 390 revision '2010-y-siguientes' boundary (2015, 2016) differs only in
    which boxes the two designs declare -- no box moved, no page length changed, no slot changed
    occupancy -- and the verdict does not name it, so the box comparison is reading displacement
    only and a box added or removed is invisible to every signal

The mutation reds this assertion and no other besides the deliberately-red span verdict, so it isolates the signal rather than breaking the module. The plugin **refuses rather than passing** on four no-op conditions: the helper being absent, the rebinding not taking, the verdict builder resolving a different object than the one rebound, and - the positive control that matters most - the helper failing to report on a synthetic removed box, or reporting on pure movement, either of which would mean suppressing it does not isolate membership.

    uv run --no-sync ruff format --check <this module>   All checks passed
    uv run --no-sync ruff check <this module>            All checks passed!
    uv run --no-sync ty check <this module>              All checks passed!

## Notes

**One gap remains and it is attributed.** Modelo 390 2018/2019 shows zero movement, zero membership change, identical page lengths and zero occupancy transitions. Only the description-keyed pass can see it, via a Regimen Simplificado slot changing from a Lorca-specific reduction to a generic one at a fixed offset and width. That is a separate open row, and it is the last of the three gaps this instrument had against the independent union.

**The instrument now carries four signals, and the module docstring still says three.** The heading was already wrong by one before this Step, was corrected to three, and is now wrong by one again in the same direction. It is corrected here rather than left for the next reader to trip over, on the same reasoning as before: a module that miscounts its own instruments invites a reader to act on the ones it names and miss the rest.

**Not measured.** Whether the description-keyed pass finds boundaries beyond 2018/2019 is unknown until it lands. The reconciliation this feeds must re-derive the union at the time it runs rather than inherit 21 or 22 as a literal, must report the confirmed subset separately from the reviewed-but-rejected ones, and must carry in the same sentence as any corpus-wide figure that Modelo 390's 2004 to 2014 designs are bundled only as xsd, fall outside the parsers' accepted suffixes and were never read.

**Attribution.** The source change was swept into HEAD by a peer bare whole-index commit before it could be committed here, the third such incident on this Step's module. The working tree is byte-identical to HEAD, so the state tested is the state that shipped, but the commit history attributes the change to a subject describing unrelated work.
