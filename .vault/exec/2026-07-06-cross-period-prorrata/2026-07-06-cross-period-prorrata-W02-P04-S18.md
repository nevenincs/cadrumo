---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:0f787e406a6709d905cadcf482c1e670eac3fdeb47884c7c29c024e1fe754222'
step_id: 'S18'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# add tests for override precedence and both observation cross-check surfaces (blocking contradiction vs informational regulated-difference notice)

## Scope

- `src/aeat/application/prorrata_register/tests/test_overrides.py`

## Description

- Add real encrypted-register tests proving AEAT-authorised and inicio candidates outrank a carried prior definitive candidate in the application lookup.
- Add a real filed-observation test proving a carried prior definitive entry that contradicts the prior observation blocks with `observation_revision_value_divergence`.
- Add real filed-observation tests proving AEAT-authorised and inicio regulated differences surface non-blocking `regulated_prorrata_override_difference` notices naming the provenance.

## Outcome

`W02.P04.S18` is implemented. Override precedence and both cross-check surfaces now have committed tests over real repository objects and registry-grounded prior Modelo 303 observations.

Verification:

- `uv run --no-sync ruff check src\aeat\application\prorrata_register\tests\test_overrides.py src\aeat\application\prorrata_register\_seed.py src\aeat\application\prorrata_register\__init__.py`
- `uv run --no-sync pytest -q src\aeat\application\prorrata_register\tests\test_overrides.py src\aeat\application\prorrata_register\tests\test_seed.py src\aeat\application\prorrata_register\tests\test_service.py`

## Notes

No mocks, skips, xfails, new resolver convention, or new binding source kind were introduced. This closes the `W02.P04` implementation/test row set.

`uv run --no-sync vaultspec-core vault check all --feature cross-period-prorrata --json` remains non-clean because of out-of-scope vault hygiene diagnostics: existing template annotations in older cross-period-prorrata plan/audit/reference/exec records, the already-unreferenced research warning for the feature, the plan's pre-existing research-reference warning, and global feature-rename-integrity errors in unrelated exec folders. The step-owned closure gates were `vault check features -f cross-period-prorrata --json` and `vault check frontmatter --json`, both clean.
