---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:563aec213478828b894ab6d07eb640d1bd9b34553814b279ab21836305b387cf'
step_id: 'S80'
related:
  - '[[2026-08-24-registry-completeness-closure-plan]]'
  - '[[2026-08-16-registry-campaign-sequencing-designless-modelo-registry-membership-adr]]'
  - '[[2026-08-24-registry-completeness-closure-modelo-721-structured-message-design-and-filing-boundary-reference]]'
  - '[[2026-08-10-aeat-export-fragment-generator-authority-plan]]'
---
# Reconcile Modelo 721 structured-message filing authority with the positional-only export predicate: obtain the required ADR decision and enroll source taxonomy, authority-grade gate, canonical exporter, and local emitted-payload proof under the existing export plan while preserving Modelo 136 terminal refusal.

## Scope

- `.vault/adr/`
- `.vault/reference/`
- `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md`
- `src/cadrumo/domain/calculations/registry/_validate_export_exemption.py`
- `src/cadrumo/domain/calculations/registry/tests/test_export_exemption_declared.py`

## Description

- Used Vaultspec-RAG across code and ADR corpora, then read the governing
  registry, export, and Modelo 721 authorities in full and confirmed exact
  symbols with `rg`.
- Audited semantic and exact-name overlap for Modelo 721 serializers, export
  dispatchers, source-kind predicates, render profiles, and live proof stores.
- Amended the accepted registry-membership decision in place to recognize
  the future exact, hash-pinned structured-message-contract boundary without
  claiming that a Modelo 721 package is already enrolled or weakening the
  evidence boundary for visual forms.
- Assigned the future source taxonomy and contract gate, canonical SOAP
  request-XML export, and production emitted-payload proof to the open S97-S99
  rows in the existing export-fragment authority plan.

## Outcome

Modelo 721 is an authorable structured-message filing gap, not a terminal
absence and not a positional-layout task. The accepted architecture now keeps
one source-artifact taxonomy, one `ExportLayoutFormat` vocabulary, one
`application.filing.export_draft` dispatcher, and one live filing-export proof
authority. Structured proof must validate production-emitted bytes against the
pinned XSD and source-grounded semantic paths; it cannot use fixed-width offset
probes, a direct serializer call, or a remote response as substitute evidence.

This is an architectural and owner-routing outcome only. No Modelo 721 SOAP
contract package, typed source kind, structured export layout, serializer, or
proof branch ships today. S97 must first acquire distinct 2023 and 2024
contract-package inventories, including exact package/member hashes and legal,
revision, and law-selected filing-context scope. S98 and S99 must then add the
single canonical export and proof branches against the selected package. All
three Steps remain open, and this Step remains unchecked until its correction is
independently re-reviewed.

Modelo 136 remains terminal under current evidence because a visual form and
procedure guidance do not satisfy the machine-contract predicate. Modelo 721
also remains applicability-only and non-fileable until S97-S99 and the separate
source/casilla owner work land for each exact exercise era.

## Notes

- No production code, registry source row, filing grade, or output capability
  changed in this architecture/enrollment Step.
- The redeclaration audit found no Modelo 721 writer, semantic map, render
  profile, proof entry, or parallel proof store. The only adjacent duplicate
  risk is today's repeated raw source-kind strings; S97 replaces them with the
  canonical typed taxonomy and predicate rather than adding another local set.
- The canonical-source audit confirms the current `SourceReference.kind` and
  `ExportLayoutFormat` vocabularies do not yet contain a structured-message
  member. The future taxonomy, selected-package authority, export branch, and
  proof branch remain S97--S99 work rather than a claim this correction makes.
- The previously proposed positional-only coverage ADR was not accepted and is
  not used as implementation authority; the accepted membership ADR is the one
  governing record amended here.
