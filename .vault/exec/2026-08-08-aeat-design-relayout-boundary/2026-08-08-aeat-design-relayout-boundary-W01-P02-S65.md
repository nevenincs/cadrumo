---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:48c71386610414229abfc63fd4a6bbd32e5266682fc86b763f86102b40b31285'
step_id: 'S65'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Assert the reserved-to-real occupancy transition alongside the retirement direction

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`

## Description

- Test the gate's own recorded claim that the reverse occupancy direction measures zero across the bundled corpus, through the gate's own helpers rather than a reimplementation.
- Report both occupancy directions as boundary evidence, keeping each direction's diagnostic text truthful about which side reserves the position.
- Add the companion guard that neither direction may contribute to the verdict over a corpus that cannot show it, gated on the property rather than on a tally.
- Correct the module's own instrument count, which named two signals while three shipped.
- Prove the guard bites by mutating from outside the repository.

## Outcome

**The row's own stated premise was wrong, and correcting it is the finding.** The row said the reverse direction lacked positive cases until the occupancy inventory is re-keyed on the design file, which the still-open re-keying row would supply. Measured through the gate's own occupancy, source-inventory and claimed-years helpers with the inventory exactly as it ships today, the reverse direction has **32 transitions across four modelos and twelve boundaries**, against **16** for the retirement direction that was already asserted. The reverse direction is not the weaker half and never was: it is twice the size of the half that shipped.

So the gate's recorded rationale - that reserved to real "measures zero across the whole bundled corpus, so an assertion for it would ship vacuous and pass silently forever" - was not an artefact of the one-design-per-year keying, as this executor previously reported and as the row text encoded. It was simply never checked against the corpus it described. A rationale for withholding an assertion is itself a measurement, and this one was reasoned rather than run. This Step therefore did **not** need the re-keying row to land first, and it is no longer blocked by it.

Both directions now contribute to the verdict. The harm is symmetric and equally invisible to the other instruments: a slot revived out of reserved space is a field the later design declares and the earlier one does not, so a filing written under the earlier layout cannot declare that quantity at all, while a retirement is the same event with the two sides exchanged. Neither moves a box, changes a page length, or alters a digest.

**The boundary set grew by one.** Modelo 303 bounded historical revision moves from 4 re-layouts needing 5 revisions to **5 re-layouts needing 6**, the new one being **2017/2018**, which the revival direction is the only signal in the module to name. Modelo 390 stays at 6, Modelo 303 open-ended at 3, Modelo 200 at 1. The new boundary sits below the computed prescripcion edge of 2022, so **the in-window scope does not change and no authoring row was added or removed**. The excluded-boundary list grows by one entry, Modelo 303 2017/2018, which is a scope-narrowing note rather than new work.

The companion guard is gated on the **property**, not on a count. It asserts each direction has at least one instance anywhere in the corpus, never how many. Pinning today's 16 and 32 would encode this moment, train the next author to bump two constants, and then detect nothing; the counts move every time AEAT publishes. It deliberately spans the whole corpus rather than one revision's claimed span, because a positive case anywhere proves the signal is live while requiring one inside every span would fail on modelos that simply never re-layout.

The module's own heading claimed **two** independent signals while three shipped, an undercount that predates this change and that invites a reader to act on the two it names. Corrected to three, with the correction stated rather than quietly applied.

## Verification

    uv run --no-sync python <scratch>/probe_revive.py
    TOTAL across every exporting revision's claimed span, YEAR-KEYED (as shipped):
      retired into reserved : 16
      reserved -> real      : 32

    uv run --no-sync pytest <this module> -p no:randomly -n0 -q -rA
    PASSED ...::test_both_occupancy_directions_have_a_positive_case_in_the_corpus
    FAILED ...::test_no_revision_spans_a_design_relayout
    modelo 303 revision '2009-y-siguientes' spans 5 re-layout(s) and needs 6 revisions

Mutation proof, from **outside** the repository so nothing under source control changed and a crash leaves no residue. A plugin on the interpreter path rebinds the module's reserved-text pattern to one that cannot match any AEAT description, collapsing both directions to zero:

    PYTHONPATH=<scratch>/mut uv run --no-sync pytest <this module> -p erase_reserved -p no:randomly -n0 -q -rA
    MUTATION APPLIED: _RESERVED_FIELD rebound, holder confirmed, _occupancy reads the rebound object
    FAILED ...::test_both_occupancy_directions_have_a_positive_case_in_the_corpus
    AssertionError: no slot anywhere in the bundled corpus is RETIRED into reserved space, so that
    half of the occupancy signal can no longer fail and its contribution to the verdict is vacuous

The plugin **refuses rather than passing** if the rebinding is a no-op: it fails loudly when the attribute is absent, when the pattern it holds does not match real AEAT reserved text, when the rebinding does not take, when the mutated pattern still matches, and - the case a naive monkeypatch misses - when the occupancy helper resolves a different object than the one rebound. A no-op mutation otherwise prints APPLIED and every test passes, which reads exactly like a gate that does not bite.

Positive control on the mutation's reach: the clean verdict carries 4 occupancy-evidence lines and the mutated verdict carries **0**, so the mutation demonstrably reached the measurement path rather than only the guard.

    uv run --no-sync ruff format --check <this module>   1 file already formatted
    uv run --no-sync ruff check <this module>            All checks passed!
    uv run --no-sync ty check <this module>              All checks passed!

## Notes

**A correction to this executor's own earlier report.** The prior Step Record and the report that followed it attributed the reverse direction's absence to the one-design-per-year inventory and cited five positive cases in Modelo 303 alone. The five cases are real but the attribution was wrong: the direction has cases under the shipped year-keyed inventory too, in four modelos. The row text encoded the wrong premise because this executor authored it from that wrong attribution, and it is corrected here rather than left standing.

**No sibling gate was disturbed.** A sweep for any other site pinning this signal, its diagnostic text or a boundary count found this module alone, so the overlapping-gate hazard did not materialise. The other five tests in the module pass unchanged.

**The gate remains red and must.** The span assertion is landed red as the campaign's specification, and this change makes it name one boundary more rather than fewer. That is the intended direction.

**Not measured.** Whether the revival direction names further boundaries once the three inventories are re-keyed on the design file was not measured here, because that re-keying has not landed. The 32 figure is a floor under the current keying, not a total.
