---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:b3d16bee851ccd28bd2d3f914927ec2169ab73fe1865962ce2496eeb1488ea97'
step_id: 'S28'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-04-user-docs-search-consolidation-deterministic-casilla-enrollment-research]]"
---

# Reconcile Diseño verification contract

## Scope

- `dev/docs/terminology/tests/test_resolution.py`

## Description

- Ground the stale Diseño verification expectation with settled vaultspec-rag searches over `_resolution.py`, the registry projection, and ADR Update 9.
- Update only the existing model-only Diseño case in `dev/docs/terminology/tests/test_resolution.py` to assert `DroppedHit(NO_TARGET_ENTITY)`.
- Obtain a source-only LUNA extra-high review of the exact hunk and preserve unrelated legal-test peer edits.

## Outcome

The verification expectation now matches the resolver and ADR contract: a model-only non-TOML Diseño workbook hit without an individual casilla locator is dropped with `DropReason.NO_TARGET_ENTITY`. The LUNA extra-high review returned PASS and confirmed the change is limited to the intended function, retaining the M036 path and helper.

P06.S28 remains open for the deferred verification lane because no tests were authorized or run. This record proves source alignment, not runtime or full-green acceptance.

## Notes

- No tests, builds, model downloads, live sweeps, RAG reindexing, Pagefind/runtime probes, generated artifacts, or deployment were run.
- Unrelated legal-test edits in the same file were preserved and excluded from the S28 change.
- The next evidence required for closure is the authorized test/verification run; the standing deployment deferral remains unchanged.

### 2026-08-06 authorized execution

The stale model-only Diseño expectation is covered by the marker-aware resolver run: the consolidated source gate returned `63 passed in 180.00s (0:03:00)`. The production resolver therefore remains fail-closed for a model-only non-TOML hit without an individual locator; no undocumented locator schema was invented.
