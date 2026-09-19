---
tags:
  - '#research'
  - '#aeat-design-relayout-boundary'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:d6710634a6ed9a705ecbe45eebf1c486ec7056b557f216157084086238afead7'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
  - "[[2026-08-07-aeat-design-relayout-boundary-adr]]"
---

# `aeat-design-relayout-boundary` research: `Modelo 200 export fragment tree provenance (W01.P02.S78)`

## Findings

## Sources

## Context

## Question (W01.P02.S78)

Establish how Modelo 200's existing 149-file export fragment tree (encoding 6,537 fields) was actually authored, since the design offers no unique field-to-slot key (per W01.P02.S77, only 36.7% of fields pair unambiguously against the published design). Read the commit that introduced it and its exec record first, then whether a mapping tool existed and was removed, then whether the fragments carry provenance beyond `source_refs`.

## Answer

The tree was authored by hand/agent transcription from the AEAT Diseno de Registros workbook, with no parsing tool in existence at the time, and it carries no per-field provenance beyond a bulk-stamped `source_refs`/`legal_refs` pair identical across every field.

### Evidence chain

1. **Today's 149 fragments are a refactor, not the original artifact.** Commit `8938bde0` (2026-05-19) deleted a 132,896-line `2024-y-siguientes.toml` and split it into the current fragment tree. The real origin is upstream of that split.
2. **The bulk content landed in one commit.** `cdcd5b11` (2026-05-06, "Implement secure persistence and registry slices") took the file from 264 to 132,816 lines. The same commit landed the AEAT DR workbooks as corpus (`01-200-ejercicio-2025-10-9-mb-xls.xlsx` and siblings) - the workbook and the encoding arrived together.
3. **A mapping tool existed, and predates the tree.** The DR-spec ingestion authority (`_ingest.py`, 239 lines), its test, and DR-spec JSON fixtures (`dr303e24.json`, 3,768 lines - Modelo 303, not 200) were deleted in `97dac2be7`, 2026-05-04 - two days BEFORE `cdcd5b11` authored the tree. The tooling was not removed after generating the Modelo 200 tree; it was gone before the tree was written, and its fixtures were for a different modelo entirely. The 2026-05-21 ADR amendment records the removal as sanctioned.
4. **The governing ADR states the method outright.** `2026-04-22-aeat-fichero-boe-export-adr` Sec.3: "Each modelo's `_RECORD_SPECS` tuple is hand-authored from the canonical BOE Orden."
5. **Provenance beyond `source_refs` - none.** Across all 149 fragments the only provenance keys are `legal_refs` and `source_refs`. `source_refs` is the single constant `["aeat-dr-200-2025"]` on every one of the 6,537 fields; `legal_refs` is one identical 19-article block on every field, including literal envelope fields with no legal basis at all. This is bulk-stamping, not per-field derivation - no digest, no cell anchor, no page/row reference, no transcription marker.

### Correction to the row's premise

S78 characterises the tree as encoding fields "against a design offering no unique field-to-slot key" - true of the design, but the tree itself is not unkeyed. A direct parse finds 148 records, 6,537 fields, of which 5,300 (81.1%) carry a `casilla_id`, referencing 3,248 distinct casillas. Every one of those 3,248 resolves against the 3,250 declared casilla fragments (2 declared but never exported). The tree's internal casilla<->field linkage is complete and self-consistent.

What was never established is the EXTERNAL pairing to the design's own slot numbering. S77's 36.7% match rate is therefore not a degraded mapping but the signature of a tree transcribed independently of the design's slots - confirming S77's conclusion ("the tree was never derived from a design") from the authoring side rather than the measurement side. Field count cross-checks exactly against S77's 6,537, confirming both instruments count the same population.

### What this bounds

- The S78 conditional fires: the mapping is unverified against AEAT and cannot serve as a "parsed-never-transcribed" reproduction fixture. It proves internal self-consistency, not fidelity to the published design. Any later Wave treating it as an AEAT-grounded oracle needs rescoping.
- Nothing is recoverable from the deleted `_ingest.py` tooling for Modelo 200 - it predates the tree and its fixtures were for Modelo 303.
- A related defect surfaced in passing: `source_refs = ["aeat-dr-200-2025"]` sits on the `2024-y-siguientes` revision - the same design-year-versus-claimed-year mismatch `test_layout_design_applies_to_claimed_years` reports for modelo 303/390/720. The tree's sole provenance pointer names a design year the revision itself does not claim to cover. Likely belongs to that same revision-span family of findings rather than to S78 specifically, recorded here for traceability.

Investigation stopped at the answer per the row's own instruction ("stop at the answer rather than exhausting the list").
