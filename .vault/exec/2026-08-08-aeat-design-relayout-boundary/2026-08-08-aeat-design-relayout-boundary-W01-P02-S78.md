---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:99ad5599065085d8b3ebe97d543b750a9e94e0fe3fa8a9c79e6ed0ad716c257d'
step_id: 'S78'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---

# Establish Modelo 200's export fragment tree provenance and author method

## Scope

- `.vault/research/2026-08-09-aeat-design-relayout-boundary-modelo-200-fragment-tree-provenance-research.md`

## Description

Investigated the origin and authoring method of Modelo 200's 149-file export fragment tree encoding 6,537 fields.

## Outcome

**The tree was hand/agent transcribed from the AEAT Diseno de Registros workbook.** No parsing or generation tool existed to convert the design into fragments. The tree carries no per-field provenance beyond a bulk-stamped, identical `source_refs = ["aeat-dr-200-2025"]` and `legal_refs` pair on every field, including envelope-only fields with no legal basis.

**The mapping is UNVERIFIED against AEAT** — confirmed by cross-checking field count (6,537 exact) against S77's design-pairing measurement, which found only 36.7% of fields match the published design's own slot numbering. The tree's internal casilla-to-field linkage is self-consistent (3,248 casillas, 5,300 fields with IDs resolve correctly), but that internal consistency proves nothing about fidelity to the AEAT design's published slot numbering.

**Verdict: S78 conditional fires.** The mapping cannot serve as a "parsed-never-transcribed" reproduction fixture. A later Wave treating it as AEAT-grounded oracle must rescope that expectation.

## Notes

The deleted `_ingest.py` mapping tool (removed 2026-05-04, before the tree was authored 2026-05-06) predates the tree entirely and its fixtures were for Modelo 303, not 200. Nothing is recoverable from it for reproducing the Modelo 200 authoring method.

A related finding: `source_refs = ["aeat-dr-200-2025"]` sits on the `2024-y-siguientes` revision, which does not claim to cover 2025 design year — a design-year-versus-claimed-year mismatch that likely belongs to the larger revision-span family of findings rather than here, recorded for traceability.
