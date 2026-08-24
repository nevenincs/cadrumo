---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:1eb415a568a73e62f66025a39500a2cb579740e49bb5c78737fe080178bac762'
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
three Steps remain open.

The independent correction re-review in
`2026-08-24-registry-completeness-closure-s80-correction-rereview-audit`
recorded no findings against corrected ADR commit `3a90ceb74a`. The normal
plan-state reconciliation may therefore close S80: it has delivered the required
accepted decision and exact owner routing, without treating the future S97--S99
implementation as completed.

Modelo 136 remains terminal under current evidence because a visual form and
procedure guidance do not satisfy the machine-contract predicate. Modelo 721
also remains applicability-only and non-fileable until S97-S99 and the separate
source/casilla owner work land for each exact exercise era.

## Verification

- Vaultspec-RAG located the accepted membership ADR, the registry-completeness
  plan and the canonical closure/export authorities. Targeted `rg` then confirmed
  exactly one `SourceReference` declaration, `ExportLayoutFormat` declaration,
  `application.filing.export_draft` writer, and `LiveFilingExportProofAuthority`.
- The exact Modelo 721 census finds no structured-message source kind, source
  package, typed layout, serializer, renderer, proof entry, or parallel proof
  store. `application.calculations._foreign_asset_redeclaration` is a
  registry-grounded, non-filing advisory for annual foreign-asset changes, not
  export implementation and therefore no writer redeclaration.
- The independent audit passed the six Modelo 721 registry tests and two Modelo
  136 terminal-versus-owner worklist tests. This plan/record reconciliation does
  not alter production code or rerun their unchanged proof surface.

## Notes

- No production code, registry source row, filing grade, or output capability
  changed in this architecture/enrollment Step.
- The canonical-source audit confirms the current `SourceReference.kind` and
  `ExportLayoutFormat` vocabularies do not yet contain a structured-message
  member. The future taxonomy, selected-package authority, export branch, and
  proof branch remain S97--S99 work rather than a claim this correction makes.
- The previously proposed positional-only coverage ADR was not accepted and is
  not used as implementation authority; the accepted membership ADR is the one
  governing record amended here.
