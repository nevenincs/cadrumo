---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W07.P27.S164'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# declaracion-extraction-architecture W07.P27.S164

Added `corpus_round_trip_verified: bool = False` to `ExtractionProfileDefinition` and authored `validate_declaracion_pdf_round_trip_gate` — the build-time enforcer that fires when a `declaracion_pdf` profile has corpus fixture PDFs but neither `corpus_round_trip_verified` nor `provisional_pending_specimen` is set. Wired the new gate alongside the existing specimen gate in `validate_extraction_profile_section`. Updated the existing `test_provisional_specimen_gate` to match the strengthened gate contract (fixture-present happy-path now requires `corpus_round_trip_verified = true`).

## Files modified

- `src/aeat/domain/calculations/registry/_schema.py` — new field `corpus_round_trip_verified: bool = False`
- `src/aeat/domain/calculations/registry/_validate_extraction_profiles.py` — new function `validate_declaracion_pdf_round_trip_gate`
- `src/aeat/domain/calculations/registry/_validate_record_sections.py` — invoke new gate alongside existing one
- `src/aeat/domain/calculations/registry/test_corpus_round_trip_gate.py` — 4 new unit tests (created)
- `src/aeat/domain/calculations/registry/test_provisional_specimen_gate.py` — updated fixture-present test

## Tests added / modified

**`test_corpus_round_trip_gate.py`** (4 tests):
- `test_fixture_exists_no_flags_fails` — (a) fixture present, both flags False: gate fires with `corpus_round_trip_verified` in message
- `test_fixture_exists_round_trip_verified_passes` — (b) fixture present + `corpus_round_trip_verified=True`: gate dormant
- `test_fixture_exists_provisional_flag_passes` — (c) fixture present + `provisional_pending_specimen=True`: gate dormant (opt-out wins)
- `test_no_fixture_round_trip_gate_is_dormant` — (d) no fixture: only specimen gate fires, round-trip gate is silent

**`test_provisional_specimen_gate.py`** — `test_fixture_present_no_flag_validates` renamed to `test_fixture_present_round_trip_verified_validates` and updated to set `corpus_round_trip_verified=True`, matching the strengthened discipline.

## Commit

`b4e7298ac`
