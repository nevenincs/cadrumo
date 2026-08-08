---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:27d467ccab9d45a518bee7e2df91f112bf278c4187f8b8fccde715aca88a5a3f'
step_id: 'S79'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Validate every export layout against its own declared structure

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Outcome

**Two of the five ruled checks turned out to have no intra-layout referent, and one already existed.** Established before designing anything:

- `ExportRecordDefinition` declares **no total length**, so "offsets within the record's declared length" and "declared lengths summing to the record total" are not two independent checks — both collapse into a comparison against the diseno.
- **Overlap is already validated** by `_verify_record_offsets` at layout resolution. Not duplicated; a second copy would have been the duplicate-authority defect this campaign keeps finding.

So the shipped check is the one remaining mapping-free comparison: **a record's implied extent against the largest POSICIONES its own design declares.** A maximum against a maximum pairs nothing, which is why it works where every pairing-based mechanism measured as blocked.

**The first census was wrong, and it was my instrument.** Selecting each modelo's newest readable `.xlsx` produced three apparent overshoots. Per-revision design selection through the source catalogue resolved all three:

- **Modelo 123 `2024-y-siguientes`** resolves `aeat-dr-123-2024-v20`, totals `[600]`, implied extent **600 — fits exactly**. The apparent +100 came from comparing against the 2019-2023 design at 500. The modelo the authorising record cites as the exemplary pattern is clean.
- **Modelo 303, both revisions** declare `aeat-dr-303-2025` and imply 1900, which is that design's DP30302 total. They fit because they ARE the 2025 layout — which became the finding that opened the applicability check.

**Result: zero overshoots, and that is not reported as reassurance.** Three blindnesses are recorded in the module: a layout shifted wholly within its record passes, a record stopping short of its total is invisible and legitimately so, and the comparison is against the LARGEST sheet total, so a record overflowing a smaller sheet while fitting a larger one is missed. Closing the third needs the record-to-sheet pairing the module deliberately avoids.

**Unmeasured is reported, never passed: 8 layouts.** Six are Modelo 100 XML-dictionary layouts with no record design — legitimately not fixed-width. The two that matter are **Modelo 115** and **Modelo 200**, whose designs publish no readable POSICIONES. Modelo 200 remains the modelo this campaign inspected most closely and the one this check cannot speak about.

The unmeasured set is **printed rather than asserted empty**, deliberately: requiring it empty would fail on a corpus property this module cannot fix and would invite the allowlist this campaign keeps refusing. The assertion that bites is that the MEASURED set is non-empty, so the check cannot go vacuous.

## Verification

    uv run --no-sync pytest <the new module> -p no:randomly -n0 -q
    2 passed in 23.18s

    UNMEASURED by the export-extent check (8): 6 x m100 xml-dictionary, m115, m200

    ruff check / ruff format --check / ty check   All checks passed!

## Notes

The design used for each layout is resolved through the registry's own source catalogue rather than by globbing the corpus, which is what corrected the census. Selecting by filename compared revisions against designs they do not encode and produced a 194-byte overshoot that existed only in the comparison.

**Not measured.** Whether any record overflows a smaller sheet of its own design while fitting the largest — that needs the record-to-sheet pairing this check avoids by construction.
