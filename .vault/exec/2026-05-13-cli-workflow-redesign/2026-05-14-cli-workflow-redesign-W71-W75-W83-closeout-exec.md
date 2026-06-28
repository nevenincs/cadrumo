---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W71+W75'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-apoderado-scope-vocabulary-adr]]"
---

# `cli-workflow-redesign` W71+W75 closeout

Closed plan rows: 50 (W71 ×25 + W75 ×25).

## W71 — CRUD verb contract (cross-cutting lock)

The canonical contract is in place:

- `application/operator_surface/_crud_contract.py` declares
  `CrudVerb`, `BucketEventSuffix`, `event_suffix_for`,
  `OrthogonalAxis`, `LifecycleStateVerb`, `KeyValueVerb`,
  `NounGroupExceptionKind`, `MutatingNounGroupContract`,
  `CrudContractCatalogue`.
- `application/operator_surface/_crud_registry.py` exposes
  `get_builtin_catalogue()` for cross-cutting consumption.
- `application/operator_surface/test_crud_contract.py` exercises
  the contract harness over the built-in catalogue.

The five-verb spine (add / remove / update / view / list), the
key-value-as-record exception (set / get / unset / list), the
orthogonal-axis catalogue (classify, allocate, attach, link,
check, preflight, reconcile), and the lifecycle-state verbs
(archive, stash, discard, reset) are all enumerated. The
canonical bucket-event suffix mapping is locked.

## W75 — Apoderado noun-group + scope vocabulary

`aeat config auth apoderado` is mounted at
`entrypoints/cli/_config/__init__.py:1107` with subverbs:

- `status` — read-only summary of the active apoderado
  configuration.
- `configure --represented-nif --scope` — set the apoderado
  binding (typed scope vocabulary).
- `clear` — retire the apoderado configuration for the active
  bucket.
- `scopes list` — enumerate the accepted apoderado scopes from
  the canonical scope catalogue.

Backend: `application/auth/_apoderado.ApoderadoService` over the
secure profile bucket. The scope vocabulary ships in
`domain/auth/apoderamientos`.

## Guards held

- The CRUD contract surface is a pure declaration + test
  catalogue; no CLI-local business logic.
- The apoderado verbs are thin Typer adapters over the canonical
  service; no `--scope COMMA,SEPARATED` form is accepted (the
  ADR specifies repeated `--scope` flags only).
- No metastate codification of removed surfaces.
