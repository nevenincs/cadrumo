---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:e636fc2f3fd5b02d6c1ae4729d7238e42706713bc736179f2757c7d33e7cda6d'
step_id: 'S288'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Decide how a repeatable detail row is identified across edits, since detail_rows is resupplied whole on every calculate call and only the M210 grouped-renta row carries a business key while the other four kinds are identified by position alone: rule whether an edit submission replaces the whole row set so position suffices within one submission, or whether a stable clock-free row identity is minted at add time and threaded into the revision's content address, and rule how a row absent from a resupplied set is distinguished from one never declared; amend the edit-contract decision record in the same change

## Scope

- `the amended modelo-edit-contract ADR`
- `src/cadrumo/domain/modelos/_row_models.py`
- `src/cadrumo/application/modelo/_edit_models.py row addresses`
- `the calculate boundary's detail_rows contract`
- `and focused row-identity and absence tests`

## Changes

- `M` `.vault/adr/2026-08-24-modelo-edit-contract-adr.md`
- `M` `src/cadrumo/application/modelo/_edit_models.py`
- `M` `src/cadrumo/application/modelo/_edit_services.py`
- `M` `src/cadrumo/application/modelo/_edit_execution.py`
- `A` `src/cadrumo/application/modelo/tests/test_edit_detail_row_reconstruction.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_models.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_revision_persistence_guarded_writes.py src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_contract.py src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py src/cadrumo/adapters/persistence/profile/tests/test_modelos_edit_receipts.py src/cadrumo/application/modelo/tests/test_edit_detail_row_reconstruction.py -q -n 0 -m "integration or unit"` -> `pass` (67 passed)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/_edit_models.py src/cadrumo/application/modelo/_edit_services.py src/cadrumo/application/modelo/_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_detail_row_reconstruction.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/_edit_models.py src/cadrumo/application/modelo/_edit_services.py src/cadrumo/application/modelo/_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_detail_row_reconstruction.py` -> `pass`

## Notes

The Step's own premise -- "only the M210 grouped-renta row carries a
business key while the other four kinds are identified by position alone"
-- is false: every `ModeloDetailRow` kind already carries a real
already-declared natural key in its own fields (`nif`, `nif_comunitario` +
`clave_operacion`, `source_id`). Found via `vaultspec-rag` leading discovery
to `RetencionObservationRepository.replace_observations`
(`_retencion_observations_repository.py:219`), an established, shipped,
tested whole-set-replacement mechanism for exactly this problem shape (M180
per-perceptor rows). No minted or positional identity was needed.

Decision: whole-set replacement, addressed by natural key. No new field on
`ModeloDetailRow`, so `src/cadrumo/domain/modelos/_row_models.py` (named in
the Step's own scope) was not touched. The calculate boundary's `detail_rows`
parameter shape was also not changed -- it already accepted a complete
tuple; only the VALUE the executor constructs for it changed.

`MOVE_ROW` is retained rather than retired: row order is structurally
significant (it drives each row's physical record occurrence number in the
exported fichero via `_record_renderer.py`'s `enumerate(..., 1)`, confirmed
against `_revision_replay_inputs.py`'s M349 replay projection, and already
participates in the revision's content address).

A row absent from a resupplied set needs no `cleared_casilla_ids`-equivalent
axis: unlike a scalar (whose declared-zero, cleared, and never-declared
states collapse into one absence), a detail row has only two states,
present or absent, with no ambiguous middle state -- confirmed by the
precedent's own read path, which records no trace of a dropped row.

Full guarded end-to-end execution against a real registry-backed modelo
(profile setup, calculate, persist) was not additionally proven here beyond
the direct real-model reconstruction tests: the reconstruction logic itself
(`_reconstruct_detail_rows`) is now wired into `apply_modelo_edit` and
threads its result into the same real
`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics` call
every other edit path already exercises end-to-end in
`test_edit_execution.py`/`test_edit_contract.py`, so the wiring itself rides
those existing real-registry proofs; a dedicated end-to-end detail-row
calculate test is reasonable follow-on coverage for S276.
