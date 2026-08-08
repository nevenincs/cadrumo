---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:7f388daca6e01296ffceb39991eb6b4857b1730981ed8ababf392ab8c827aa44'
step_id: 'S72'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Widen the bracketed box-number marker beyond four digits

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`

## Description

- Search for the canonical definition of the bracketed box number before writing a wider one.
- Consume that definition instead of re-declaring a width in this module.
- Assert single authority by identity, and assert that no modelo bracketing a box number reads as having none.
- Re-derive every Modelo 200 figure this campaign recorded, with the independent instrument fixed too.
- Prove it by restoring the four-digit cap from outside the repository.

## Outcome

**The fix is not a wider pattern, it is deleting a duplicate.** A semantic search for the concept found the registry already owns a canonical definition in production, `_CASILLA_TAG_RE` in the record-design coverage module, bounded at **five** digits, with its rationale fully documented. This module carried a private four-digit copy. So did two sibling test modules. One concept, four declarations, three of them wrong.

The canonical definition's own docstring records this exact failure shape, which is the strongest evidence that widening rather than consolidating would have been the wrong fix: it was once written as a fixed five-digit pattern, matched nothing on the modelos that bracket at natural width, and made the coverage report say "0 casillas, 0 gap" for 36 of the 38 revisions bundling an official design. It also records why it is bounded at five rather than left open - an unbounded pattern would admit amounts, NIF fragments and position offsets that appear bracketed in the same columns. That reasoning is deliberately not restated in this module, because restating it is how a third copy begins.

**What the four-digit cap cost.** Modelo 200 numbers its boxes with five digits. Measured on its newest bundled design, the cap keyed **23 boxes against 3440** under the canonical marker - under one percent - so the box-offset signal and the box-set membership signal were switched off for that modelo while the verdict reported nothing amiss. The description-keyed population is defined as the slots carrying no box number, so the same cap also mis-classified thousands of numbered fields as unnumbered: a candidate description pass asserted 1462 changes on Modelo 200's single boundary, samples of which are numbered fields changing box number at a fixed slot.

**Re-derived: the Modelo 200 count survived and the method did not.** The boundary count is unchanged at 1, and the union total across gated spans is unchanged at 22. That is not corroboration of the earlier figure, it is a coincidence of shape: Modelo 200's revision claims a single adjacent design pair, and that pair was already flagged by the record-set and occupancy signals. Had it claimed a third design, the count would have moved.

What changed is the evidence, completely. The gate now reports for that boundary **1140 of 3194 shared boxes moved, 246 added and 145 removed**, where it previously reported only a record-count change and an occupancy transition. The independent union pass now fires all four signals there where it fired three.

**That upgrades the divergence from the first accepted decision record from "uncovered" to "refuted".** That record rules no implementation action for Modelo 200 on the ground that its two-design span is offset-identical. The campaign had already overtaken this on a record-set-change signal, which the record's offset reasoning arguably did not address. It is now refuted on its own terms: 1140 of 3194 shared boxes relocate across that boundary. The authoring rows were re-pointed to carry the offset evidence rather than only the decomposition change.

**The instrument checking the fix carried the same defect.** The first re-derivation reported Modelo 200 unchanged at three firing signals, because the independent probe declared its own four-digit marker. Fixing only the gate and re-measuring with a blind probe would have produced a clean-looking confirmation that the boundary set was unaffected. The probe was pointed at the canonical marker and re-run, at which point the box signal appeared. This is the fifth instance in this campaign of an instrument sharing the defect it was being used to check, and the second where the checking instrument was mine.

## Verification

    uv run --no-sync pytest <this module> -p no:randomly -n0 -q -rA
    11 passed, 1 failed
    PASSED ...::test_the_box_marker_is_the_registry_canonical_one_and_reads_every_modelo
    FAILED ...::test_no_revision_spans_a_design_relayout

    modelo 200 '2024-y-siguientes' 2024/2025: 1140 of 3194 shared boxes moved (e.g. [00016] 880->897,
      [00075] 2138->2121) -- NOT a clean in-record displacement: the record set also changed
      + box SET changed: 246 added (e.g. [03401], [03402], [03403]) and 145 removed

Mutation proof, from **outside** the repository, restoring the four-digit cap:

    PYTHONPATH=<scratch>/mut uv run --no-sync pytest <this module> -p four_digit_cap -p no:randomly -n0 -q -rA
    MUTATION APPLIED: four-digit cap restored, holder confirmed, modelo 200 newest design keys 23
      boxes against 3440 under the canonical marker
    FAILED ...::test_the_box_marker_is_the_registry_canonical_one_and_reads_every_modelo

The plugin **refuses rather than passing** on four no-op conditions: the marker being absent, the canonical marker already failing to read a five-digit box, the four-digit pattern still matching one, and - the positive control that matters - the cap failing to key fewer boxes than the canonical marker on a real design, in which case it blinds nothing and could red nothing.

    uv run --no-sync ruff format --check <this module>   All checks passed
    uv run --no-sync ruff check <this module>            All checks passed!
    uv run --no-sync ty check <this module>              All checks passed!

The assertion is on IDENTITY with the canonical object, not on a digit width. Pinning five would recreate the defect one modelo later and would make this module an independent authority on the pattern again, which is what went wrong. Its companion asserts that no design bracketing a box number keys zero boxes here, which is the check that would have caught the original defect: a modelo that parses designs but reads no boxes is unread, and reports identically to one with nothing to find.

## Notes

**Two sibling copies remain and were deliberately not touched.** A declared-box-number gate holds both a four-digit marker and a four-digit shape test applied to registry casilla numbers, and a rate-keyed gate embeds a four-digit marker in a row pattern. Both are separate modules with their own semantics, one of which imports from this one, and editing them blind risks reddening gates whose behaviour was not measured here. They carry the same blindness on Modelo 200 and need their own row.

**Records corrected rather than quietly restated.** The union record's Modelo 200 line said "union 1, gate 1, no gap" and now says plainly that the agreement was worthless as evidence because both sides shared one defect, that the count survived and the method did not. The plan's Modelo 200 paragraph and both Modelo 200 authoring rows now carry the offset evidence.

**Not measured.** Whether the corpus contains bracketed box numbers wider than five digits was not established beyond the exporting modelos sampled here; the canonical definition's bound is inherited along with its reasoning rather than re-verified. The description-keyed pass remains unauthored, so Modelo 390's 2018/2019 boundary is still reported by no signal in the module.
