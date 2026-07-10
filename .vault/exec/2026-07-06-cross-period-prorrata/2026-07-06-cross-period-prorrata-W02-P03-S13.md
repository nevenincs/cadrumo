---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S13'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# add tests for the seed happy path, divergence-blocks, and missing-stamp-advises paths against real filed observations

## Scope

- `src/aeat/application/prorrata_register/tests/test_seed.py`

## Description

- Add real encrypted-observation seed tests for the carried-prior-definitive happy path.
- Add a divergent `stamped_revision_id` test that blocks the seed with a registry-revision-divergence finding.
- Add a legacy missing-stamp test by deleting the stamp key from an encrypted saved observation, preserving current-write stamping and explicit-null refusal.
- Allow calculation-observation payloads whose legacy wire shape omits `stamped_revision_id` to load with `None` while keeping explicit `null` invalid.
- Align the shared revision carry gate contract so generic carry readers fail closed on `None` stamps.

## Outcome

`W02.P03.S13` is implemented. The committed tests cover all three requested seed outcomes against real `CalculationObservationRepository` rows backed by the encrypted secure-object store:

- matching prior settlement stamp seeds a `carried_prior_definitiva` register entry with `303:2025:4T` source identity;
- divergent prior settlement stamp produces a blocking `registry_revision_divergence` finding and no seed;
- legacy field-absent prior settlement payload produces a non-blocking `missing_legacy_revision_stamp` advisory and still seeds the carried entry.

Verification:

- `uv run --no-sync ruff check src\aeat\application\calculations\_observations_repository.py src\aeat\application\prorrata_register\tests\test_seed.py`
- `uv run --no-sync pytest -q src\aeat\application\prorrata_register\tests\test_seed.py`
- `uv run --no-sync pytest -q src\aeat\application\calculations\tests\test_revision_stamp_roundtrip.py src\aeat\application\prorrata_register\tests\test_seed.py`
- `uv run --no-sync ruff check src\aeat\application\calculations\_observations_repository.py src\aeat\application\calculations\_revision_carry_gate.py src\aeat\application\prorrata_register\tests\test_seed.py`

## Notes

Initial test collection exposed that the new `prorrata_register/tests` directory is not a package; the test imports were changed to absolute `aeat...` imports. The first repository compatibility attempt used a model-level pre-validator, which interfered with strict JSON datetime parsing; the final implementation uses a field-level validator scoped to `stamped_revision_id`. No mocks, skips, xfails, or fabricated calculation oracles were introduced.

`uv run --no-sync vaultspec-core vault check all --feature cross-period-prorrata --json` remains non-clean because of out-of-scope vault hygiene diagnostics: existing template annotations in prior cross-period-prorrata plan/audit/exec records, an already-unreferenced research warning for the feature, the plan's pre-existing research-reference warning, and global feature-rename-integrity errors in unrelated exec folders. The step-owned feature gates used for closure were `vault check features -f cross-period-prorrata --json` and `vault check frontmatter --json`, both clean.
