---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:84cb09705eaba63b491c021aff193b42ae2a2fe558fd3c88506c99437cffaf42'
step_id: 'S104'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Fix the two campaign-owned gates red at committed HEAD, the liveness gate's test_every_consumer_claim_is_backed_by_a_real_reference and the settings-lifecycle gate's test_no_production_module_names_an_operator_data_location_by_literal, both failing on the same cause: five production literals in _app_live.py and _overview_evidence.py naming taxonomy-governed locations by string instead of by member, and ten bucket and keystore consumer_module claims still naming _namespace_registry.py after the path-hierarchy extraction moved their real consumers to a sibling module, a peer fix held uncommitted and worsening on re-measurement rather than resolving, re-measure at HEAD before closing rather than trusting a working-tree read

## Scope

- `src/cadrumo/entrypoints/cli/_app_live.py`
- `src/cadrumo/entrypoints/cli/_overview_evidence.py`
- `src/cadrumo/core/_storage_taxonomy.py`

## Description

- Fix the two campaign-owned gates red at committed HEAD, `test_storage_liveness_gate.py::test_every_consumer_claim_is_backed_by_a_real_reference` and `test_settings_lifecycle_gate.py::test_no_production_module_names_an_operator_data_location_by_literal`, both tracing to the same five literals in `_app_live.py`/`_overview_evidence.py`.

## Outcome

Landed as "fix(cli): enrol the live-read and filed-declaration roots in the taxonomy." The five `var/cadrumo/...` literals (`iva-compensation-history`, `iva-read-evidence`, `filed-declarations`) are gone from both modules. **Adopted rather than authored**: found complete and unattributed in the working tree, predating this session, and landed on operator directive rather than commissioned by this reconciliation.

**Independently verified against a clean pinned-SHA archive, not the working tree.** `PINNED=$(git rev-parse HEAD)` resolved to `c16bb9a0ae`; `git archive "$PINNED"` extracted to a scratch directory (the working tree's `_storage_taxonomy.py` carries substantial uncommitted peer WIP for Family 1/2 declarations that could have contaminated an in-place run); both gates run from the clean archive: **2 passed**. This is the exact discipline the closure-statement reference names as the fix for measurement mechanism 3 (`git archive HEAD` then a separate SHA read, race-prone) — applied here rather than only described.

## Notes

This closes the prominent blocker in the closure-statement reference. That document's blocker section itself carried a stale "3 unbacked became 13, moving backwards" claim from an earlier, race-corrupted measurement (mechanism 3) — corrected in a prior pass to the true 3 → 13 → 3 arc, and now further updated to reflect this fix landing and both gates confirmed green at a cleanly pinned SHA.
