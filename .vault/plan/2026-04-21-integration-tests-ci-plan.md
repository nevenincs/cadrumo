---
tags:
  - "#plan"
  - "#integration-tests-ci"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-integration-tests-ci-adr]]"
  - "[[2026-04-21-integration-tests-ci-research]]"
---

# `integration-tests-ci` plan

## Phase 1 — Marker-driven collection

### Step 1.1 — `conftest.py` at repo root

Implement `pytest_collection_modifyitems` hook honouring `AEAT_FIXTURE_OFFLINE` + `AEAT_FIXTURE_L2_ENABLED` + `AEAT_FIXTURE_L3_ONLY`.

### Step 1.2 — Self-tests

`tests/test_conftest_tier_selection.py` verifying the env-driven selection logic produces the expected keep/skip lists.

## Phase 2 — Quality-metric plugin

### Step 2.1 — `tests/_quality_metric.py`

Pytest plugin registered in root `conftest.py`. Emits `test-results/extraction-quality.json`.

### Step 2.2 — JSON schema

Strict pydantic `QualityMetricReport` record; JSON round-trip stable.

### Step 2.3 — Tests

Plugin tested against a mini synthetic pytest run.

## Phase 3 — L1 anchor fetcher

Already authored under cluster C plan; this phase wires it into CI via `.github/workflows/ci.yml` + marker-driven collection.

## Phase 4 — Kent workflow integration tests

### Step 4.1 — `tests/integration/test_kent_workflows.py`

Parametrised Kent scenarios per research §6. Initially empty placeholder awaiting cluster-D extractor landings; each extractor PR adds its own test case.

### Step 4.2 — CI step

Existing `pytest -m unit` already collects these (they carry `@pytest.mark.unit`). No new step needed — they run alongside the rest.

## Phase 5 — Drift-detection workflow

### Step 5.1 — `.github/workflows/l1-anchor-drift.yml`

Scheduled weekly + workflow_dispatch. Opens an issue on drift.

### Step 5.2 — Script `scripts/fetch_l1_anchors.py --check-drift` flag

Extension to the cluster-C fetcher: fetches URL fresh, compares SHA-256, exits non-zero on mismatch + prints drift details.

## Phase 6 — Audit + docs

- Subagent code review per phase.
- `docs/concepts/ci-quality-metrics.md` explaining the artifact and how to read it.

## Exit criteria per phase

- CI duration < 10 min per runner on a mid-size PR.
- `AEAT_FIXTURE_L3_ONLY=1 uv run pytest -m unit` completes under 3 min locally.
- Drift workflow runs without exception on a no-drift week.
- Kent workflow tests all pass.

## Kent UX roleplay

Not directly Kent-facing; the roleplay is the *contributor's* experience: "A maintainer opens a PR that subtly breaks Modelo 303 extraction. CI fails on `test_kent_imports_modelo_303_declaracion_post_sept_2024` with a clear message. The maintainer notices, reads the quality-metric artifact diff, fixes the regression before merging."

## Non-goals

- No PR quality-regression gate in MVP.
- No auto-PR-from-scheduled-workflow (drift opens issues, not PRs).
- No Windows-specific tweaks unless/until needed.
