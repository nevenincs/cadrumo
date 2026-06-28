---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]'
---



# `cli-workflow-redesign W61.P303.S1818` Code Review



W61.P303.S1818-001 | HIGH | Caller-supplied ledger values can bypass bucket-local aggregation when the bucket emits no value

`calculate_modelo_revision_from_bucket_aggregation` is intended to route modelo calculation through the work unit's bucket-local transaction catalogue, but its merge guards only reject caller input when a bucket-derived key already exists with a different value. In `src/aeat/application/modelo/_actions.py:648`, `_merge_bucket_binding_values` receives `ledger_bindings.binding_values` plus caller `binding_values`; in `src/aeat/application/modelo/_actions.py:675`, `_merge_bucket_binding_values` only flags keys that are present in `bucket_values`; in `src/aeat/application/modelo/_actions.py:704`, `_merge_bucket_bound_inputs` only flags `casilla_inputs` that conflict with already-resolved bound inputs.

That leaves a bypass for every ledger-backed binding/casilla that the current bucket catalogue does not emit, including an empty catalogue or a bucket with rows filtered out by period/category/readiness. For Modelo 303, the registry declares `modelo-303-iva-repercutido-general-cuota` as `ledger_iva_aggregation` and `iva.repercutido.general` as the bound casilla for that binding. A caller can invoke the bucket-aggregation path with no matching bucket-local transaction rows and still pass `binding_values={"modelo-303-iva-repercutido-general-cuota": ...}` or `casilla_inputs={"iva.repercutido.general": ...}`. The calculation then persists those values as if they were part of the bucket-aggregation calculation path.

This violates the S1818 bucket-local catalogue requirement and the ADR constraint that modelo preparation receives normalized bucket-local facts, not caller-provided substitutes for ledger facts. The guard should reject caller-supplied values for ledger-derived binding ids and their bound casillas regardless of whether aggregation produced a value, while still allowing legitimate non-ledger manual inputs. Add real-behavior tests covering an empty bucket and a missing ledger category/period to prove the caller cannot supply a ledger binding id or ledger-bound casilla through this path.

Review summary: one HIGH finding, no CRITICAL findings observed. The scoped tests in `src/aeat/application/modelo/test_bucket_aggregation_flow.py` use real SQL-backed secure storage and no mock/skip/xfail shortcuts by text scan, but they do not cover the absent-bucket-value bypass above. Targeted verification through `.venv\Scripts\python.exe -m pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py -q` passed with 2 tests.

## Remediation Re-review 2026-05-14

W61.P303.S1818-001 | RESOLVED | Caller-supplied ledger values can no longer bypass bucket-local aggregation when the bucket emits no value

The remediation in `src/aeat/application/modelo/_actions.py` resolves the prior HIGH finding. `_merge_bucket_binding_values` now receives the registry revision and rejects every caller-supplied binding id owned by `ledger_iva_aggregation` or `ledger_renta_expense_aggregation`, independent of whether the active bucket produced a value for that binding. `_merge_bucket_bound_inputs` now derives ledger-bound casillas from the same registry-owned binding set and rejects caller-supplied casilla inputs for those bound casillas before delegating to the generic calculation path.

The added tests in `src/aeat/application/modelo/test_bucket_aggregation_flow.py` cover the specific bypass cases from the original finding: empty-bucket ledger binding injection and empty-bucket ledger-bound casilla injection. The existing conflict test was also tightened to expect the stronger rejection semantics for any caller-supplied ledger binding, not only mismatched values.

Focused verification through `.venv\Scripts\python.exe -m pytest src/aeat/application/modelo/test_bucket_aggregation_flow.py -q` passed with 4 tests. A text scan found no mock, fake, monkeypatch, skip, or xfail shortcuts in the focused test file.

Remediation review summary: the prior HIGH finding is resolved. No remaining HIGH or CRITICAL issues were observed in the remediation scope.
