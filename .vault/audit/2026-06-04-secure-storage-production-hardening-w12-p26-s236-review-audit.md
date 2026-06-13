---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S236]]'
  - '[[2026-06-03-modelo-export-evidence-parity-adr]]'
  - '[[2026-06-03-modelo-export-workbook-parity-adr]]'
  - '[[2026-06-03-modelo-export-visual-design-adr]]'
---

# `secure-storage-production-hardening` `W12.P26.S236` Review

## S236-001 | PASS | Modelo export is a plaintext export exception

`src/aeat/application/modelo/_export.py` writes an operator-selected local
fichero-BOE artefact and appends a `MODELO_EXPORTED` bucket event. The event
continues through the bucket-event repository, while the output file is an
intentional operator-facing plaintext artefact. The affected-file row was
therefore corrected from stale `manifest-discovery` to `plaintext-exception`
with the `plain-file` signal added.

## S236-002 | PASS | Export ADRs constrain this boundary

The accepted 2026-06-03 evidence, workbook parity, and visual-design ADRs were
reviewed. This step preserves the fichero-BOE export path while hardening
storage and refusal boundaries; it does not claim the shared workbook builder,
Evidencia tab, offline/online workbook materialiser parity, visual style facets,
or official-layout parity gate. It does enforce the evidence ADR's already-landed
rule that ledger-derived revisions without bundled evidence or a resolvable
snapshot reference are refused before export.

## S236-003 | PASS | User-facing export refusals are locale-backed

Raw export refusal messages were replaced with `application.modelo.errors.*`
locale keys and structured context for missing ledger evidence, non-exportable
revision state, missing operator profile/name facts, unmappable period tokens,
cross-bucket export refusal, draft approval failure, and file write failure.
Cross-bucket and output-write refusals no longer echo bucket identifiers or
operator filesystem paths.

## S236-004 | PASS | Cleanup diagnostics do not swallow root causes

The `.tmp` export artefact cleanup path now routes through a helper that logs
cleanup failures at debug level via the project logger and omits the
operator-selected path from the log message. Cleanup exceptions no longer mask
the original draft-write or bucket-event failure.

## S236-005 | PASS | RAG duplication search confirms export ownership

`vaultspec-rag search "modelo export calculation parity workbook evidence ADR"
--type vault --port 8766 --max-results 12` surfaced the accepted export
evidence, workbook parity, and visual design ADRs plus their execution records.

`vaultspec-rag search "modelo export storage boundary active profile manifest
bucket" --type code --port 8766 --max-results 12` clustered active-profile
export guards, modelo export tests, locale leaves, runtime storage readiness,
and `_export.py`; it did not identify another modelo fichero-BOE export owner.

## S236-006 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/modelo/_export.py src/aeat/application/modelo/test_export.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/modelo/test_export.py` passed with 14 tests.
- `python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `vaultspec-core vault plan check` reported only the existing `PLAN022 line 0` warning.

Disposition: close `AFR-134` as `plaintext-exception`.
