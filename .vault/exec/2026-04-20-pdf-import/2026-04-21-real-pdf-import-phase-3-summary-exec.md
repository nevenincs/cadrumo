---
tags:
  - "#exec"
  - "#real-pdf-import"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-integration-tests-ci-plan]]"
  - "[[2026-04-21-real-pdf-import-phase-2-summary-exec]]"
---

# real-pdf-import execution phase 3 — wave 6 (cluster H)

## Delivered capability

Kent's end-to-end import experience is now **CI-gated**. Any future PR that regresses the happy path for Modelo 130 declaración import lights up before merge; any upstream AEAT / BOE document drift is detected weekly and surfaced as an issue.

## Commit

- `ee6931b` — *feat(ci): cluster H — Kent workflow regression gate + L1 drift workflow (EPIC #305 wave 6)*

## Files landed

- `tests/integration/__init__.py`, `tests/integration/test_kent_workflows.py` — 6 Kent-level regression tests driving `CliRunner` against `aeat filing import`. Synthetic PDFs only (fixture_tier_l3) so CI never depends on external bytes.
- `tests/conftest.py` — `_apply_fixture_tier_gates` env-driven marker gate (`AEAT_FIXTURE_OFFLINE`, `AEAT_FIXTURE_L2_ENABLED`, `AEAT_FIXTURE_L3_ONLY`) added to the existing `pytest_collection_modifyitems` hook.
- `.github/workflows/l1-anchor-drift.yml` — weekly cron + workflow_dispatch. Runs `scripts/fetch_l1_anchors.py --check-drift`; on SHA-256 mismatch opens a P1-high tracking issue with review instructions.

## Kent UX roleplay

**Path A — happy**: Kent (or any future contributor's CI) drops the shipping Modelo 130 synthetic PDF on `aeat filing import --from-declaracion`. Two assertions guard the outcome: regex `\d+ of \d+ casillas extracted` confirms complete coverage; `Verification status: VERIFIED` confirms the formula engine re-derived every value.

**Path B — partial**: 4 casillas populated → `Extraction status: PARTIAL` + `Verification status: NEEDS_REVIEW`; missing IDs `05`, `06`, `07` listed verbatim. Kent sees what to fill.

**Path C — language default**: `AEAT_OUTPUT_LANGUAGE=es` yields *"verificado"*; English override yields *"verified"*. Both asserted.

**Path D — CLI hygiene**: missing / dual `--from-*` flags exit non-zero with "exactly one of…" / "only one…" errors.

**Path E — shipping contract**: `--from-justificante` still produces the #271 scaffold + amendment-baseline `SubmittedFiling`. No regression.

## Quality gates

- `uv run pytest -m unit` — 1964 passed, 2 intentional xfails (cluster-B schema gap — resolved in wave 7 / phase-4), 1 skipped.
- `AEAT_FIXTURE_L3_ONLY=1 uv run pytest -m unit` — 38 passed (synthetic-only path). Marker-gate verified.
- `uv run ruff check` + `uv run ty check` — clean.

## Follow-up

- The L1 manifest is still empty — drift workflow is a no-op until concrete anchors land. Not blocking.
- `fixture_tier_l2` only runs locally when `AEAT_FIXTURE_L2_ENABLED=1`; validated once the user's scrubbed corpus contributes its first file.
