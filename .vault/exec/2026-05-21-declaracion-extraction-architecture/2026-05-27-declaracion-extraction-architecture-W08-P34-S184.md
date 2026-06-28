---
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: "2026-05-27"
modified: '2026-05-27'
step_id: "S184"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-27-declaracion-extraction-architecture-audit]]"
---

# declaracion-extraction-architecture W08.P34.S184

## Step

Add production-path tests for both gate validators exercising `RegistryValidator` with `source_root=bundled_path()` rather than direct `corpus_root` injection.

## What was done

Surveyed all test functions in `test_provisional_specimen_gate.py` and `test_corpus_round_trip_gate.py`, classified each by construction pattern (direct injection vs production wiring), then added the missing production-path tests to `test_corpus_round_trip_gate.py`.

**Pre-survey classification:**

| Test | Pattern |
|------|---------|
| `test_provisional_field_defaults_false` | No validator |
| `test_provisional_field_accepts_true` | No validator |
| `test_no_fixture_no_flag_fails_validation` | Direct injection |
| `test_no_fixture_with_flag_validates` | Direct injection |
| `test_fixture_present_round_trip_verified_validates` | Direct injection |
| `test_corpus_root_derived_from_bundled_path` | **Production path** (pre-existing) |
| `test_gate_fires_no_fixture_no_flag` | Production source_root + direct corpus |
| `test_fixture_exists_no_flags_fails` | Direct injection |
| `test_fixture_exists_round_trip_verified_passes` | Direct injection |
| `test_fixture_exists_provisional_flag_passes` | Direct injection |
| `test_no_fixture_round_trip_gate_is_dormant` | Direct injection |

**Verdict on broader pattern:** The pattern was real and present. The round-trip gate test file had ZERO production-path tests before this step — every test used direct `justificante_corpus_root` injection via `_validator_with_corpus()`. This is the same coverage gap that silenced the specimen gate. The corpus_root derivation bug was not isolated.

**New tests added to `test_corpus_round_trip_gate.py`:**

- `test_corpus_root_derived_from_bundled_path` — asserts that `RegistryValidator(catalogues, source_root=_DATA_ROOT)` (no injection) derives a non-None, directory, `justificantes`-named corpus root. Mirrors the specimen gate equivalent.
- `test_round_trip_gate_fires_via_production_path` — constructs the production-wired validator, uses M130 (which has real corpus fixtures) with both flags False, asserts `corpus_round_trip_verified` error fires through production wiring.
- `test_verification_source_gate_fires_via_production_path` — per task #3: asserts the `verification_source` gate (added by concurrent agent #49) also fires via production wiring with `corpus_round_trip_verified=True` and `verification_source=None`.

**Concurrent interaction:** The concurrent agent for #49 landed `verification_source` schema field and additional direct-injection tests for that rule before this step completed. The `_committed_profile()` helper in `test_corpus_round_trip_gate.py` was updated by that agent to accept `verification_source`. My additions integrate cleanly with those changes. Confirmed 19/19 pass in the clean run at 52.48s before the concurrent agent introduced temporary TOML syntax errors in `036.toml` and `193/` which broke the shared `@cache`d registry load.

## Files changed

- `src/aeat/domain/calculations/registry/test_corpus_round_trip_gate.py` — 3 new production-path tests added

## Test result

`19 passed in 52.48s` (clean run before concurrent TOML corruption from #49/#51).
