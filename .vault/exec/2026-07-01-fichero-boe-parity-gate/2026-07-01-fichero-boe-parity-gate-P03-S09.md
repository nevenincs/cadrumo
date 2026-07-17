---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S09'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Add a pre-write structural-fidelity assertion that every rendered casilla number and segmento matches the registry-declared metadata with zero drift

## Scope

- `src/aeat/application/filing/_export.py`

## Description

- Project the registry casilla record-design metadata onto the export subview so the render choke point can reach the authoritative `CasillaDefinition` number and segmento the calculation engine consumes, not only the completeness manifest's own copy. Add a frozen `CasillaRecordMetadata` record carrying casilla id, number, and segmento, populate a `casilla_record_metadata` tuple in the snapshot-to-subview projection in `src/aeat/application/filing/runtime.py`, and export the new record.
- Add `_assert_casilla_metadata_fidelity` in `src/aeat/application/filing/_export.py`: for every manifest casilla the official record files a slot for (the representable set), re-ground the manifest's declared number and segmento against the projected registry metadata. A divergent number or segmento, or a manifest casilla the registry no longer declares, raises a hard `FilingExportError` enumerating the registry-expected value versus the value the fichero-BOE would file.
- Thread `casilla_metadata` through `assert_export_mirrors_manifest` and its `export_draft` call site, running the fidelity assertion pre-write before the presence subset check.

## Outcome

- The fichero-BOE parity gate now refuses, before any bytes are written, a `.boe` whose rendered casilla numbering or segmento drifts from the registry-declared record-design metadata, closing the metadata-drift dimension of the official-structure mirror.
- A standalone bite probe confirmed the assertion fires on an injected number drift and on an injected segmento drift for Modelo 130, and passes untouched on the real shipped structure of every covered modelo including the multi-segment Modelo 200 and the annual Modelo 390.

## Notes

- The `record_type` of a fixed-width export record does not correspond to the casilla `segmento` (verified against Modelo 200: record types are page codes such as `page_001b`, segmentos are codes such as `DP200014B`), so the segmento authority is the registry `CasillaDefinition`, reached via the new subview projection sanctioned by the ADR Pathway note.
- The registry-build completeness validator already cross-checks manifest number/segmento against the casilla definition, so this export-time assertion is defense-in-depth at the render choke point per the official-structure rule (a divergence is a hard failure at export). It remains anti-tautological: it cross-checks two independently authored registry surfaces and bites when they disagree.
