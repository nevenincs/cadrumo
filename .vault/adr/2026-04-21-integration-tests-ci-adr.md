---
tags:
  - "#adr"
  - "#integration-tests-ci"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-integration-tests-ci-research]]"
  - "[[2026-04-21-real-pdf-fixture-corpus-adr]]"
  - "[[2026-04-21-declaracion-extractor-adr]]"
  - "[[2026-04-21-calc-verification-adr]]"
---

# `integration-tests-ci` adr: `tier-gated-collection-quality-metric-artifact-drift-detection` | (**status:** `accepted`)

## Problem Statement

Cluster H ties everything to CI so Kent-level regressions fail the build, AEAT template drift opens an issue, and per-modelo quality is observable over time.

## Considerations

- Cluster C's `fixture_tier_l1 / l2 / l3` markers are informational; cluster H wires them to pytest collection + CI opt-in.
- `AEAT_FIXTURE_OFFLINE=1` already used elsewhere in the repo; extend convention.
- CI already runs on Ubuntu + Windows / Python 3.13 (`.github/workflows/ci.yml`). Additions layer on.
- Kent UX regressions are what the user cares about — a dedicated `tests/integration/test_kent_workflows.py` file makes them loud.

## Constraints

- No regression of existing CI duration (< 10 min target).
- L1 fetching respects `AEAT_FIXTURE_OFFLINE=1`.
- L2 off by default; no leakage of private filings in CI logs.
- Drift-detection workflow is a separate `.yml` — no cross-coupling.
- Quality-metric JSON is artifact-only in MVP; no PR gate.

## Implementation

### 1. `pyproject.toml` pytest options

Add `markers` entries (already in cluster C plan) + `addopts` convention for deselection via env vars:

```toml
[tool.pytest.ini_options]
addopts = "--strict-markers"
```

A `conftest.py` at repo root implements an env-driven `pytest_collection_modifyitems` hook that deselects:

- `fixture_tier_l1` when `AEAT_FIXTURE_OFFLINE=1` **and** the anchor file isn't in `.cache/l1_anchors/`.
- `fixture_tier_l2` when `AEAT_FIXTURE_L2_ENABLED` is not `1`.

### 2. `scripts/fetch_l1_anchors.py` + CI integration

Described in cluster C plan §4.2; this cluster wires it into CI as a step before `pytest`.

GH Actions job additions in `.github/workflows/ci.yml`:

```yaml
- name: Fetch L1 anchors
  run: uv run python scripts/fetch_l1_anchors.py
- name: Run tests
  run: uv run pytest -m unit --maxfail=10 --tb=short --junit-xml=junit.xml \
       -o tmp_path_retention_policy=failed
  env:
    AEAT_FIXTURE_OFFLINE: "0"
    AEAT_FIXTURE_L2_ENABLED: "0"
- name: Upload quality metric artifact
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: extraction-quality-${{ matrix.os }}
    path: test-results/extraction-quality.json
```

### 3. Quality-metric hook

`tests/_quality_metric.py` (pytest plugin):

- Registers a pytest hook `pytest_runtest_logreport` that accumulates per-test pass/fail grouped by markers (`(modelo, template_revision, tier)` extracted from test names or attached markers).
- Writes `test-results/extraction-quality.json` at session finish.

### 4. Drift-detection workflow

New file `.github/workflows/l1-anchor-drift.yml`:

```yaml
name: L1 anchor drift
on:
  schedule:
    - cron: "0 5 * * 1"   # 05:00 UTC every Monday
  workflow_dispatch:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv run python scripts/fetch_l1_anchors.py --check-drift
      - name: Open issue on drift
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.create({...})   # cite the drifted anchor
```

### 5. Kent workflow integration tests

`tests/integration/test_kent_workflows.py` per research §6 — parametrised over Kent's common scenarios. All L3-tier (synthetic), no external dependencies. Run every CI build.

### 6. Out of scope

- No PR-quality-regression gate (future enhancement).
- No auto-update of `docs/coverage/modelos.md` from the metric JSON (future scheduled workflow).
- No Windows-specific L1 anchor fetching tweaks unless Windows-specific failures observed.

## Consequences

- Kent UX is CI-enforced: any regression breaks the build.
- AEAT template drift raises GitHub issues automatically — no silent bit rot.
- Per-modelo quality is observable over time via artifacts.
- L2 private fixtures never leak into CI logs.
- CI stays under 10 minutes with tier deselection (L2 off by default; L1 cached).
