---
tags:
  - '#plan'
  - '#live-justificante-reconcile'
date: '2026-06-10'
tier: L2
related:
  - '[[2026-06-10-live-justificante-reconcile-adr]]'
  - '[[2026-06-10-live-justificante-reconcile-research]]'
---


# `live-justificante-reconcile` `live-sourced justificante reconciliation` plan

### Phase `P01` - Snapshot persistence foundation

Typed justificante-capture snapshot model, secure-object namespace, repository and lifecycle service mirroring Borrador100, gated by a strict roundtrip and an anti-tautology proof.

- [x] `P01.S01` - Register the live justificante-capture secure-object namespace at FINANCIAL sensitivity and re-export it, verified by the namespace registry test; `src/aeat/adapters/persistence/storage/_namespace_registry.py`.
- [x] `P01.S02` - Author the JustificanteCaptureSnapshot payload (modelo via core Modelo enum, filing_year, period, expediente_id, csv, pdf_sha256, pdf_bytes, official source_kind, lifecycle), object-key, content-addressed id, repository and SnapshotService hooks mirroring Borrador100.; `src/aeat/application/live/_justificante.py`.
- [x] `P01.S03` - Prove the persistence boundary with a strict secure-storage roundtrip (every defaultable field non-default), a supersession lifecycle test, and an anti-tautology mutate-on-disk proof.; `src/aeat/application/live/tests/test_justificante_capture.py`.

### Phase `P02` - Live capture orchestration

Period-aware expediente resolution and the require_live_read-gated async orchestrator that pulls the justificante via capture_justificante and persists the snapshot.

- [x] `P02.S04` - Add the require_live_read-gated async capture_justificante_snapshot orchestrator (period-aware expediente resolution, capture_justificante, service.capture) and promote it plus the service to the package top-level re-exports.; `src/aeat/application/live/__init__.py`.
- [x] `P02.S05` - Prove period disambiguation (1T vs 2T resolve to distinct expedientes, never the wrong quarter) and orchestrator wiring offline with a real service and a seam-injected session.; `src/aeat/application/live/tests/test_justificante_capture_resolution.py`.
- [x] `P02.S06` - Add a live end-to-end capture test gated by AEAT_LIVE_TESTS_ENABLED that pulls and persists a real justificante, env-driven and never xfail or skip-marker; `src/aeat/application/live/tests/test_justificante_capture_live.py`.

### Phase `P03` - Official evidence and cross-period gate

Stamp the captured justificante as official evidence under aeat_sede_live_capture so a dependent period clears MISSING_JUSTIFICANTE_VERIFICATION.

- [x] `P03.S07` - Stamp the captured justificante as official evidence (aeat_sede_live_capture observation plus ExternalEvidence on the filing record) reusing the import_external_filing_evidence single-writer pattern.; `src/aeat/application/live/_justificante.py`.
- [x] `P03.S08` - Prove a dependent period whose only upstream evidence is the live capture no longer raises MISSING_JUSTIFICANTE_VERIFICATION, and that a non-official kind still would.; `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.

### Phase `P04` - Reconcile against the persisted artefact

Materialise persisted pdf_bytes to a transient path and run the unchanged local modelo_reconcile, preserving the parser path-redaction privacy behaviour.

- [x] `P04.S09` - Add the reconcile-from-persisted seam that materialises stored pdf_bytes to a transient readable path, runs the unchanged local modelo_reconcile, and preserves the parser path-redaction behaviour.; `src/aeat/application/live/_justificante.py`.
- [x] `P04.S10` - Prove reconcile against a persisted live capture yields the expected verdict and that no caller-controlled path leaks into error messages.; `src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py`.

### Phase `P05` - CLI surface, locales and docs

New aeat app live justificante capture verb mirroring the expedientes CLI, with locale parity and regenerated API stubs.

- [x] `P05.S11` - Add the aeat app live justificante capture/list/view verbs mirroring the expedientes CLI, with typed result payloads.; `src/aeat/entrypoints/cli/_app_live_justificante_cli.py`.
- [x] `P05.S12` - Register the justificante sub-app on the live read command group, verified by the live read subgroups test; `src/aeat/entrypoints/cli/_app_live.py`.
- [x] `P05.S13` - Add the cli.app.live.justificante locale keys across all four catalogues through the aeat.locales CLI, verified by parity and translation-honesty gates; `src/aeat/locales/en.yml`.
- [x] `P05.S14` - Regenerate the API reference stubs for the new modules via the apidocs CLI and gate documented-command conformance plus scaffold --check.; `docs/api/aeat.application.live.rst`.

## Description

This plan bridges the orphaned live justificante capture into the modelo
reconciliation flow, per the accepted ADR and its research. Today the operator
must hand-download a justificante PDF and pass it to the local-only
`modelo_reconcile`, even though `capture_justificante` already pulls the
authentic AEAT-signed PDF read-only into a typed `SedeCapture`. The work adds a
new `JustificanteCaptureSnapshotService` under `application/live/` as a stateful
`SnapshotService` sibling of `Borrador100`, keyed on the
`(modelo, filing_year, period)` axis, behind `require_live_read()`. It persists
the captured `pdf_bytes` as an encrypted, content-addressed secure object under
the official `source_kind` `aeat_sede_live_capture`, which both feeds reconcile
and clears the cross-period `MISSING_JUSTIFICANTE_VERIFICATION` gate. A new
`aeat app live justificante capture` verb mirrors the expedientes CLI; the
existing local `modelo_reconcile` is consumed unchanged against the persisted
artefact via a transient temp-path materialisation for the path-only parser.

No new persistence machinery is invented: the snapshot model, namespace,
repository, and CLI all mirror established `application/live/` siblings. The one
genuinely new piece of logic is period-aware expediente resolution -
`find_expediente(modelo, ejercicio)` does not disambiguate by period, so a
quarterly work unit must narrow to its own quarter rather than silently
reconciling against the wrong receipt; `P02.S05` is the dedicated gate for that
risk. CSV authenticity via `verify_csv` is recorded in the ADR as a deferred
increment and is out of scope for this plan.

## Steps



## Parallelization

`P01` (persistence foundation) lands first and gates every later phase: the
payload model, namespace, and service are the substrate the orchestrator,
evidence stamp, and reconcile seam all consume. Within each phase the code Step
precedes its test Step (`S02` before `S03`, `S04` before `S05`, `S09` before
`S10`). `P02` depends on `P01` (the orchestrator calls `service.capture`); the
live test `S06` is an opt-in surface that may land any time after `S04` and runs
only under `AEAT_LIVE_TESTS_ENABLED`. `P03` (evidence stamp) and `P04` (reconcile
seam) both depend on `P02` but are independent of each other and may run in
parallel. `P05` depends on the `P02` service surface for the capture verb; within
it, `S11` precedes `S12` (registration needs the sub-app), while the locale
(`S13`) and docs (`S14`) Steps are independent of each other and may run in
parallel once the CLI modules exist. Three Steps re-touch
`application/live/_justificante.py` (`S02`, `S07`, `S09`); they are sequenced
`S02` then `S07` then `S09` to avoid two agents editing the module concurrently.

## Verification

The plan is complete when every Step is closed (`- [x]`). Mission success
criteria, each a verifiable gate:

1. The secure-storage roundtrip and anti-tautology proofs (`P01.S03`) pass with
   every defaultable field populated non-default, and a mutated on-disk payload
   raises rather than re-defaulting.
2. Period disambiguation (`P02.S05`) proves a 1T and a 2T work unit resolve to
   distinct expedientes, never the wrong quarter.
3. The live capture test (`P02.S06`) is green under `AEAT_LIVE_TESTS_ENABLED` and
   is gated by the environment flag, not by an xfail or skip marker.
4. A dependent period whose only upstream evidence is the live capture no longer
   raises `MISSING_JUSTIFICANTE_VERIFICATION` (`P03.S08`), while a non-official
   source kind still does.
5. Reconcile against a persisted live capture (`P04.S10`) yields the expected
   verdict, `modelo_reconcile` retains no live branch, and no caller-controlled
   path leaks into error messages.
6. The CLI conformance, locale parity, translation-honesty, and
   `apidocs scaffold --check` gates (`P05`) are clean, and the full
   `src/aeat` suite plus a structural audit pass on the integrated branch.
