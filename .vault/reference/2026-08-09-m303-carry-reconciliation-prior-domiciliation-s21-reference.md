---
tags:
  - '#reference'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:170ea39619caa5732eae8aeb683880e093b97973eebaf2bb0140341ab45acdb1'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
  - "[[2026-06-21-m303-carry-reconciliation-adr]]"
---
# `m303-carry-reconciliation` reference: `S21 prior-domiciliation election implementation reference`

## Summary

S21 models the page-three marker as the distinct `PriorDomiciliationElection` axis. `KEEP` is the neutral blank default. `CANCEL_OR_MODIFY` renders `X` only for a Modelo 303 rectificativa joined to an accepted external baseline and its official submitted-file U evidence. The 2023-2025 and 2026 layouts are separate, byte-proven snapshots: marker offsets 406 and 440, respectively. Safe receipt, event, and observation provenance retains semantic and baseline join coordinates only; it never retains an IBAN.

## Decision and scope

`PriorDomiciliationElection` is a filing election, not amendment kind, payment election, or a rectification header. Unsupported modelo, unsupported amendment kind, raw or unknown election values, missing baseline proof, or a layout without the marker must refuse before bytes, receipt, event, or filing observation.

The S21 surface deliberately exposes the typed election needed by S19 but does not implement the S19 Nota-3 DID predicate. No election carries an IBAN, rendered header, or other account material.

## Baseline-U evidence chain

The cancellation/modification path is fail closed in `src/cadrumo/application/modelo/_prior_domiciliation.py`.

1. Read `CalculationRevision.amends_filing_record_id` as the explicit baseline link.
2. Require an accepted, externally evidenced baseline `ModeloRecord` with the same bucket, modelo, year, and period as the rectificativa. The baseline may already be superseded.
3. Load the official persisted observation for that exact target and require its `aeat_justificante_csv` metadata value to equal the baseline external-evidence reference.
4. Require `ResultDispositionProjection` with `provenance_kind = source_header` and disposition `DOMICILIACION` (`U`). Profile data, casillas, `aeat_tipo_solicitud`, amount inference, and a local export do not establish this proof.

`PriorDomiciliationElectionProjection` retains only the semantic election, baseline filing id, evidence reference id, submitted-header locator, and U disposition. It is persisted through the observation envelope, filing record event payload, and export receipt by `src/cadrumo/application/calculations/_observations_repository.py`, `src/cadrumo/application/modelo/_revision_persistence.py`, and `src/cadrumo/application/modelo/_export.py`.

## Registry boundary

The old `2023-y-siguientes` revision is bounded through 2025. Its page-three marker is `prior_domiciliation_action` at offset 406 and casilla 111 is at offset 424, grounded to `aeat-dr-303-2025` and the official 2025 DiseÃ±o de Registro extract.

The separately grounded `2026-y-siguientes` revision starts on 2026-01-01. It moves the full page-three fragment to the 2026 DiseÃ±o de Registro positions: marker 440, casilla 111 at 441, and adjacent fields at 323, 340, 357, 374, 391, 408, 425, 426, 427, 458, 459, and 460. It uses `aeat-dr-303-2026`.

The 2026 M303 simplified-regime authority is BOE-A-2025-25272, Orden HAC/1425/2025. Its Article 4 expressly approves the IVA simplified-regime indices, modules, and instructions for 2026. The registry binds this source as `orden-hac-1425-2025:art-4` and `boe-orden-hac-1425-2025-iva-authority`; the bundled corpus hash is `95d03306df28554c50a96b84b68aeac91c6be14a106d533af1860c8e35f9c368` for 467505 bytes. The expired 2025 HAC/1347 source remains only in the bounded 2025 revision.

## Public path and proof

The typed option defaults to `KEEP` and is threaded through export, quickfile, file action, verification/review wrappers, CLI payload output, receipt, event, and filing observation. Public CLI help and refusal text are present in `ca`, `en`, `es`, and `hu` locale catalogues.

`src/cadrumo/application/modelo/tests/test_prior_domiciliation_export_layout.py` uses the real runtime schema provider and byte renderer. It proves `X` at the authoritative marker byte in both revisions: 2025 offset 406 with casilla 111 at 424, and 2026 offset 440 with casilla 111 at 441. The focused registry and direct-debit regression suite passed 35 tests. `aeat app registry verify`, locale scaffold check, and targeted Ruff passed.
