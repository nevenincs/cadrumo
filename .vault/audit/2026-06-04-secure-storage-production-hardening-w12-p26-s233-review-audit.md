---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S233]]'
---

# `secure-storage-production-hardening` `W12.P26.S233` Review

## S233-001 | PASS | Modelo actions orchestrate secure runtime repositories

`src/aeat/application/modelo/_actions.py` coordinates modelo work-unit,
calculation-revision, verification-report, filing-record, bucket-event, and
workflow-run lifecycle actions. Durable local modelo state is delegated to
domain repositories that resolve runtime-created secure-object repositories,
rather than local plaintext JSONL stores or direct SQL routing inside the
application action module.

## S233-002 | PASS | Remote-provider signal is bounded to workflow and filing gates

The action module wires `SubmissionEngine`, `select_provider()`, and workflow
gates for verify/file transitions. Those are live-provider orchestration
surfaces, not persistence ownership. The row therefore remains `remote-mirror`
because the file coordinates live filing/readiness gates while persisting audit
and modelo state through secure runtime repositories.

## S233-003 | PASS | Export ADRs constrain downstream builders, not this storage row

The 2026-06-03 modelo export evidence/workbook parity ADRs were reviewed. This
step does not claim workbook materialisation, evidence-tab rendering, or BOE
byte-shape parity. It verifies that the action layer now calls the extracted
IVA wallet gate helpers and that calculation/verify/file state remains routed
through the canonical repositories those export surfaces later consume.

## S233-004 | PASS | User-facing action guard errors are localised

Remaining raw Modelo action guard failures in the reviewed surface were moved
to locale keys with structured context: IVA-wallet decision shape/identity
guards, ledger preflight refusal, calculation/amendment/import registry
root/snapshot failures, unknown amendment/import casillas, source-bound casilla
override refusal, and duplicate external-import revision refusal. Locale leaves
were authored through `python -m aeat.locales set`, then verified with
`python -m aeat.locales audit`.

## S233-005 | PASS | RAG duplication search supports single IVA wallet gate owner

`vaultspec-rag search "Modelo 303 IVA wallet prior compensation gate" --type
code --port 8766 --max-results 12` clustered production gate ownership in
`src/aeat/application/modelo/_iva_wallet_gate.py`, with `_actions.py` no longer
retaining the deleted local constant/helper implementation. The remaining
compatibility alias in `_actions.py` points at the extracted helper so older
imports continue to resolve without duplicating business logic.

`vaultspec-rag search "modelo actions secure object repository orchestration"
--type code --port 8766 --max-results 12` clustered modelo secure persistence
in `src/aeat/domain/modelos/_runtime_repository.py` and domain repositories,
supporting the runtime-repository classification.

## S233-006 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_actions.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/modelo/test_actions.py` passed with 24 tests.
- `uv run --no-sync pytest -q src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_import_flow.py` passed with 27 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "modelo or s85_runtime"` passed with 10 selected tests.
- `python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

## S233-007 | OBSERVATION | Workflow run marker settings remain adjacent follow-up

`WorkflowRunRepository.save()` still resolves the returned marker path with a
direct `Settings()` constructor in `src/aeat/application/workflow/_persistence.py`.
The encrypted workflow run payload is still secure-object backed, and `_actions.py`
passes workflow runs through `WorkflowRunRepository(objects=bv_repo.secure_object_repository)`;
the remaining settings-construction cleanup belongs to the workflow persistence
owner rather than this modelo action row.

Disposition: close `AFR-131` as `remote-mirror`.
