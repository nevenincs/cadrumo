---
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: "2026-05-27"
modified: '2026-05-27'
step_id: "S194"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-27-declaracion-extraction-architecture-W08-P34-S184]]"
---

# declaracion-extraction-architecture W08.P34.S194

## Step

Tighten the production-path gate coverage from a single "fires" scenario to full Scenario A/B/C coverage for the round-trip gate, and add `test_gate_fires_via_production_path` to the specimen gate with honest documentation of the coverage boundary.

## What was done

### Round-trip gate (`test_corpus_round_trip_gate.py`)

Added two new pure-production-wiring tests alongside the existing `test_round_trip_gate_fires_via_production_path` (Scenario A):

- `test_round_trip_gate_provisional_flag_silences_via_production_path` (Scenario B): constructs `RegistryValidator(catalogues, source_root=_DATA_ROOT)` — no corpus injection — mutates M130's profile to `provisional_pending_specimen=True`. Pre-asserts derivation returned a real dir (guards false-positive from silent None), then asserts no exception is raised. A derivation bug returning None would silently pass this test for the wrong reason, hence the guard.

- `test_round_trip_gate_verified_profile_passes_via_production_path` (Scenario C): same pure-production validator, M130 profile with `corpus_round_trip_verified=True` and `verification_source="real_aeat_corpus_pdf"`. Asserts no exception; guard pre-assertion same as Scenario B.

### Specimen gate (`test_provisional_specimen_gate.py`)

Added `test_gate_fires_via_production_path` which exercises the specimen gate via `RegistryValidator(catalogues, source_root=_DATA_ROOT)` only.

**Coverage boundary:** The specimen gate fires when no corpus fixture exists + `provisional_pending_specimen=False`. All 20+ real modelos with `declaracion_pdf` profiles have at least one real fixture under `tests/fixtures/justificantes/`, so Scenario A (gate fires) cannot be triggered via pure-production wiring without injecting an empty corpus root. This is a structural property of the fixture inventory. The test documents this boundary explicitly and covers Scenario B (provisional=True, no error) and Scenario C (verified + source, no error) via production wiring, both with derivation-guard pre-assertions.

## Honest verdict: does pure-production wiring uniquely exercise the derivation path?

**Yes, with a caveat.** The derivation path in `_validate.py` (`source_root.resolve().parents[0] / "tests" / "fixtures" / "justificantes"`) is exercised by the new Scenario B/C tests. A bug in that derivation returning `None` would cause:
- Scenario A: false pass (gate can't fire if corpus_root is None)
- Scenario B: false pass for the wrong reason (pre-assertion catches this)
- Scenario C: false pass for the wrong reason (pre-assertion catches this)

The pre-assertions on `validator._justificante_corpus_root is not None` ensure derivation bugs produce a failure message distinguishable from a gate logic failure. The direct-injection tests (using `tmp_path`) remain in place to isolate gate logic from derivation logic — they are not redundant.

**What cannot be tightened:** The specimen gate "fires" scenario (Scenario A) remains hybrid — it injects `justificante_corpus_root=empty_corpus_root` because no real modelo exists with a `declaracion_pdf` profile and no fixture. Any future test suite that adds a new `declaracion_pdf` profile without creating a fixture will exercise that scenario naturally, but it cannot be synthesized against the real corpus without modifying the registry.

## Files changed

- `src/aeat/domain/calculations/registry/test_corpus_round_trip_gate.py` — 2 new pure-production-wiring tests (Scenarios B and C); Scenario A docstring updated to label it
- `src/aeat/domain/calculations/registry/test_provisional_specimen_gate.py` — 1 new pure-production-wiring test with documented coverage boundary

## Test result

`23 passed in 39.77s`
