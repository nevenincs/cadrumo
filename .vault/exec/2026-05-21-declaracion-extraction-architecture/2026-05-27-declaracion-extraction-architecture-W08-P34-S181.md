---
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: "2026-05-27"
modified: '2026-05-27'
step_id: "S181"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-27-declaracion-extraction-architecture-audit]]"
---

# declaracion-extraction-architecture W08.P34.S181

## Step

Promote `verification_source` to a typed schema field on `ExtractionProfileDefinition` distinguishing `real_aeat_corpus_pdf` / `synthetic_from_aeat_published_text` / `historical_suppression` / `not_applicable`. Update the round-trip gate to require `verification_source` when `corpus_round_trip_verified = true`. Add unit tests covering the new gate rule.

## What was done

Added `verification_source: Literal["real_aeat_corpus_pdf", "synthetic_from_aeat_published_text", "historical_suppression", "not_applicable"] | None = None` to `ExtractionProfileDefinition`. The field defaults to `None` so all existing profiles continue to validate.

Updated `validate_declaracion_pdf_round_trip_gate` in `_validate_extraction_profiles.py`: when `corpus_round_trip_verified = true`, the gate now emits a failure if `verification_source` is `None`. This enforces that every future verified profile must explicitly declare its grounding provenance.

Updated the existing `test_fixture_exists_round_trip_verified_passes` test and the `test_fixture_present_round_trip_verified_validates` test in the specimen gate file to include `verification_source` alongside `corpus_round_trip_verified=True`. Without this, those tests would fail under the new gate.

Added new parametrized tests in `test_corpus_round_trip_gate.py`:
- `test_corpus_round_trip_verified_without_verification_source_fails` — verified=True, source=None fails
- `test_corpus_round_trip_verified_with_each_verification_source_passes[real_aeat_corpus_pdf]` — passes
- `test_corpus_round_trip_verified_with_each_verification_source_passes[synthetic_from_aeat_published_text]` — passes
- `test_corpus_round_trip_verified_with_each_verification_source_passes[historical_suppression]` — passes
- `test_corpus_round_trip_verified_with_each_verification_source_passes[not_applicable]` — passes
- `test_corpus_round_trip_not_verified_with_no_verification_source_is_dormant` — unverified + source=None still triggers the round-trip gate, not the provenance gate

## Files changed

- `src/aeat/domain/calculations/registry/_schema.py` — `verification_source` field added to `ExtractionProfileDefinition`
- `src/aeat/domain/calculations/registry/_validate_extraction_profiles.py` — provenance gate added inside `validate_declaracion_pdf_round_trip_gate`
- `src/aeat/domain/calculations/registry/test_corpus_round_trip_gate.py` — 6 new tests + helper updated
- `src/aeat/domain/calculations/registry/test_provisional_specimen_gate.py` — existing test updated to provide `verification_source`

## Commit

`fc10e874a` — H1/S181: add verification_source to ExtractionProfileDefinition + gate enforcement

## Test result

19 passed in 40.47s (gate tests + provisional specimen gate tests)
