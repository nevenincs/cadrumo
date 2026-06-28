---
tags:
  - "#research"
  - "#integration-tests-ci"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-real-pdf-import-umbrella-research]]"
  - "[[2026-04-21-declaracion-extractor-adr]]"
  - "[[2026-04-21-calc-verification-adr]]"
  - "[[2026-04-21-real-pdf-fixture-corpus-adr]]"
---

# integration-tests-ci research

## Problem

Clusters D / E / F produce extractors and a verification pipeline tested in isolation. Cluster H ties everything into CI with per-modelo quality metrics that detect AEAT template drift, scrubbed-fixture regressions, and synthetic-generator fidelity issues.

## Grounded state of CI

From the repo: `.github/workflows/ci.yml` runs on every PR (Ubuntu + Windows, Python 3.13). Steps: install → lint (ruff) → typecheck (ty) → test (pytest `-m unit`) → hooks (prek). Memory snapshot `github_actions_disabled.md` marks CI as active.

## Required additions for cluster H

### 1. Fixture-tier marker runtime behaviour

Cluster C introduced `fixture_tier_l1 / l2 / l3` markers. Currently they are informational; cluster H wires them to pytest collection:

- `AEAT_FIXTURE_OFFLINE=1` env var → deselect `fixture_tier_l1` tests that require live fetch of BOE/Manual URLs.
- `AEAT_FIXTURE_L2_ENABLED=0` env var → deselect `fixture_tier_l2` tests (CI default).
- `AEAT_FIXTURE_L3_ONLY=1` env var → keep only L3 (fast feedback in `just test-quick`).

### 2. Fixture-fetch CI step

Before `pytest`, a new CI step runs `uv run python scripts/fetch_l1_anchors.py`:

- Reads `tests/fixtures/pdf_corpus/l1_public_anchors/_manifest.json`.
- For each entry, verifies or fetches to `.cache/l1_anchors/<sha256>.pdf`.
- Fails the CI run on SHA-256 mismatch — drift detection.

### 3. Extraction-quality metric

Per modelo × template_revision, collect per-test results as they run and emit a machine-readable summary at the end of the test run. Existing pytest plugin `pytest-report-log` (or simpler: a custom pytest hook) writes to `test-results/extraction-quality.json`:

```json
{
  "schema_version": "1",
  "generated_at": "...",
  "per_modelo": {
    "130": {
      "2025.01": {
        "l3_synthetic_passes": 498, "l3_synthetic_total": 500,
        "l1_anchors_passes": 3, "l1_anchors_total": 3,
        "l2_anchors_passes": 0, "l2_anchors_total": 0
      }
    },
    "303": { ... }
  }
}
```

### 4. CI artifact upload

Add GH Actions step to upload `test-results/extraction-quality.json` + `.cache/l1_anchors/*.pdf` as artifacts. Future PRs can compare their quality metric JSON to the base commit's; a regression-detection script flags any modelo × revision with lower pass-rate than base.

### 5. Drift-detection workflow

A separate scheduled workflow (weekly cron):

- Runs `fetch_l1_anchors.py` with upstream URLs (not the cached hash-pinned copies).
- Diffs the freshly-fetched PDF bytes against the committed hash-pin.
- Opens a GitHub issue on any drift (AEAT refreshed an anchor PDF).

### 6. Kent UX integration smoke tests

A new `tests/integration/test_kent_workflows.py` file, `@pytest.mark.unit`, `@pytest.mark.fixture_tier_l3`:

Each test simulates one Kent workflow end-to-end via the CLI:

- `test_kent_imports_modelo_130_declaracion` — generates L3 synthetic → CliRunner invoke `aeat filing import --from-declaracion` → assert exit 0, draft + declaracion + verdict on disk, verdict `status=verified`.
- `test_kent_imports_modelo_303_declaracion_post_sept_2024` — same shape, verifies template auto-detection of the renumbering.
- `test_kent_imports_modelo_100_borrador` — cluster-F equivalent.
- `test_kent_re_verifies_draft_after_manual_edit` — simulates Kent editing a casilla via `aeat filing build` + re-running `aeat filing verify`.

Each test ends with an assertion block that doubles as a Kent UX roleplay record: "Kent saw verdict=verified; 19/19 casillas; no warnings." These tests fail the build on any UX regression (unexpected warning, missing verdict, wrong status).

## Cross-cluster dependency

- Cluster H blocks on clusters D (extractors exist to test) + E (verification to compose) + C (synthetic generator to feed tests).
- Cluster H unblocks the per-modelo delivery loop: each new extractor lands with its own addition to `test_kent_workflows.py` so every ship is UX-verified.

## Open questions (ADR)

1. **Quality-metric artifact consumption**: is a regression-gate PR check needed (block PRs that regress pass-rate)? Recommendation: **no gate in MVP**; artifact upload + visualisation only. Future enhancement.
2. **Weekly drift workflow frequency**: weekly is enough for AEAT's publication cadence (forms refresh annually, BOE orders occasional).
3. **L2 on CI**: default off; opt-in via `AEAT_FIXTURE_L2_ENABLED=1`. Contributor branches may flip it on to exercise local fixtures.
4. **Coverage-matrix generation**: should the quality-metric JSON drive `docs/coverage/modelos.md` updates? Recommendation: **yes, post-merge on main** via a scheduled workflow that regenerates the table and opens a PR.
