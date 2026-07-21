---
tags:
  - '#research'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
related:
  - "[[2026-05-03-calculation-truth-registry-pending-adr]]"
  - "[[2026-07-14-calculation-export-import-adjudication-reference]]"
---

# `calculation-export-import-adjudication` research: `Export and import backlog admission boundary`

This research asks which apparent export-layout and declaration-extraction
gaps are genuine implementation work. It reconciles legacy plan wording,
accepted decisions, current registry data, generic runtime paths, official
bundled authority, and real-behavior test evidence. The companion Reference
owns the detailed implementation map and candidate registers.

## Findings

### The engines already exist

`ValidatedRegistryAuthority` at
`src/cadrumo/domain/calculations/registry/_authority.py:36` is the single
validated registry authority. `export_draft` at
`src/cadrumo/application/filing/_export.py:278` renders registry layouts, and
`parse_export_payload` at
`src/cadrumo/domain/calculations/registry/_export_parse.py:65` parses the same
layout data. `parse_declaracion_bytes` at
`src/cadrumo/adapters/inbound/declaracion/_parser.py:158` is the generic
declaration-PDF parser. `write_sealed_archive` and `read_sealed_archive` at
`src/cadrumo/adapters/persistence/storage/bucket/_sealed_archive_writer.py:62`
and `_sealed_archive_reader.py:75` form a separate persistence boundary.

An absent layout or profile is therefore not evidence that a new renderer,
parser, registry provider, or archive format is missing.

### Source availability is not a mandate

The capability matrix in `dev/registry/matrix/manager.py:70` reports what a
revision declares. The new-modelo checklist at
`dev/registry/newmodelo/checklist.py:87` makes layouts and profiles conditional
on supported filing and reconciliation surfaces. A bundled record design can
prove byte layout for its applicability window; it cannot establish that the
product must generate that file or that a declaration PDF uses the same
geometry.

Legacy unchecked wording likewise records a proposal, not current authority.
The accepted central calculation-registry ADR decides how reviewed data enters
the canonical engines, but it does not make every absent optional capability a
required feature.

### Current candidate outcome

- Modelo 037 is retired and superseded by 036; active export or extraction work
  would contradict the current registry boundary.
- Modelos 309 and 360 have no legacy outbound mandate. Their official record
  designs are evidence, not backlog admission.
- Modelos 036, 184, 190, 193, 308, 322, 347, 353, 369, and 840 are conditional,
  authority-windowed export candidates. None currently has a proven current
  product mandate plus completed source-window reconciliation.
- Modelo 200 submitted-file import is delivered-equivalent through its registry
  export layout and the generic submitted-file parser. Its declaration-PDF
  profile remains gated on a real sanitized filed specimen.
- Modelo 308, 309, 322, 353, and 360 declaration-PDF candidates are also gated
  on real sanitized specimens. Record designs do not prove filed-PDF geometry.
- Modelo 100 exercise 2026 is time-gated. Bundled registry revisions and design
  authority currently stop at exercise 2025.

No candidate is currently authorized for production implementation.

## Considered options

### Implement every absent layout or profile

This maximizes apparent checklist progress but treats absence and artefact
availability as requirements. It would invite speculative registry data,
backward extrapolation across authority windows, and duplicate per-Modelo
engines. Reject.

### Treat the legacy omnibus plan as the backlog

This preserves historical wording but ignores current code, supersession,
retirement, and delivered generic behavior. It would turn stale mechanisms into
false gaps. Reject.

### Admit work through an explicit four-condition gate

A candidate proceeds only when a current mandate exists, official authority
matches the exact filing window, the canonical implementation genuinely lacks
the capability, and the candidate is neither retired nor blocked on unavailable
real evidence. Registry data and real generic-engine round trips are the only
permitted implementation shape. Choose.

## Recommendation

Persist a same-feature backlog-admission ADR that binds the adjudication plan
without replacing the central registry ADR. The new decision should make the
four-condition gate authoritative, keep the 20 candidate adjudications
independent, prohibit duplicate engines, and require the final audit to record
no successor handoff when zero candidates pass. A later genuinely new engine,
authority source, or ownership boundary would require a separate ADR.
