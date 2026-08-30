---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:2430b4c29d7a92b1ee8165e1e80991ee7d6e14783e17eb610dcbf8ba406bc470'
step_id: 'S55'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Render the workspace provenance destination as FLAT BOUNDED ATTRIBUTION: the existing provenance facet plus the per-value nested provenance on scalar and repeated-row records, with no locally synthesised edges. NARROWED, and the dropped half was verified absent rather than deferred: 'producer-supplied cycle and depth dispositions' are removed because ModeloWorkspaceProvenanceRecordV1 is a flat subject-or-None plus calculation-source row, and cycle and depth appear ZERO times in the workspace projection module. The TUI must not compute them either -- a locally derived depth or cycle marker is a causal claim no producer made, which the no-synthesised-edges half of this same row already forbids. PAGING IS THE NORMAL CASE HERE, NOT THE EXCEPTION: the graded-snapshot provenance facet fans one CalculationSourceRef out into one record PER CASILLA IT NAMES, so the count is sources times casillas rather than either alone, and a single ref touching 208 casillas yields 208 records unaided. The view must let an operator distinguish a bounded page from a complete set. THE TWO PROVENANCE SURFACES TRUNCATE AT DIFFERENT THRESHOLDS -- the facet pages at 200 and the nested per-value provenance is bounded at 64 by _MAX_PROVENANCE_RECORDS in the workspace models module -- so 'all the provenance for this value' and 'all the provenance in this facet' are DIFFERENT CLAIMS and the view must not let either read as the other. EXCLUDED FROM THIS ROW: causal-graph expansion with cycle and depth semantics remains unbuilt and requires an application-layer amendment before any view can present it

## Scope

- `src/cadrumo/entrypoints/tui/modelo/view/provenance.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/view/provenance.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/view/tests/test_workspace_provenance_and_filing.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/modelo/ -m "unit or integration" -n0 -q` -> `pass` (112 passed; the 2 failures are in `src/cadrumo/entrypoints/tui/modelo/view/tests/test_work_review.py`, peer-held and outside this Step)
