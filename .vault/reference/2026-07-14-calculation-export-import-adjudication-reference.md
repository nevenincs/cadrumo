---
tags:
  - '#reference'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-08-24'
body_hash: 'sha256:aba3dc8b04f26e638d321b471eca9509a27bfe5aebde1bb0e50de146d1de94e3'
related:
  - "[[2026-07-12-calculation-truth-registry-plan]]"
  - "[[2026-07-12-calculation-truth-registry-classification-review-audit]]"
  - '[[2026-07-14-calculation-export-import-adjudication-plan]]'
  - '[[2026-07-14-calculation-export-import-adjudication-adr]]'
---
# `calculation-export-import-adjudication` reference: `Export and import adjudication implementation map`

## Summary

This reference adjudicates the apparent export-layout and declaration-extraction backlog against accepted decisions, registered legal authority, and the implementation that already exists. The system already has one validated registry authority, one generic registry-driven export renderer/parser pair, one generic declaration-PDF parser, and a separate sealed-archive persistence format. Missing registry data or source artefacts do not, by themselves, establish a product mandate.

No export-layout candidate has yet passed the complete mandate gate. Modelo 036
is not-mandated at the current product boundary; Modelos 184, 190, 193, 308,
322, 347, 353, 369, and 840 are conditional, authority-windowed candidates that
require an explicit current product mandate before implementation. Modelos 309
and 360 have no legacy export mandate, and Modelo 037 is retired. The extraction
candidates are evidence-gated except for Modelo 200's already generic
submitted-file path; its declaration-PDF path remains evidence-gated.

## Definitions and adjudication gate

- **Registry authority** means the single validated, immutable registry snapshot loaded by `ValidatedRegistryAuthority` in `src/cadrumo/domain/calculations/registry/_authority.py:36`. A repository, accessor, or runtime schema provider is a projection over that authority, not another source of truth.
- **Export layout** means reviewed registry data describing a filing format. It is interpreted by the generic renderer and parser; it is not a Modelo-specific Python exporter.
- **Submitted file** means an AEAT fichero payload interpreted by the generic export-layout parser.
- **Extraction profile** means reviewed registry data describing fields in a declaration PDF. It is interpreted by the generic declaration parser; it is not a Modelo-specific parser class.
- **Sealed archive** means the encrypted local persistence envelope written and read by the bucket storage adapter. It preserves application evidence and recovery material; it is not an AEAT export, import, or filing format.

### Disposition taxonomy

Every completed candidate record uses exactly one disposition from this table.
Apply the rows in order. If no row applies, the record is incomplete and has no
disposition.

| Disposition | Selection rule | Backlog effect |
|---|---|---|
| `retired` | The retirement field is true. | Close the candidate. Do not create active registry or implementation work. |
| `not-mandated` | Retirement is false and the mandate status is `absent`. | Close the candidate unless an accepted decision or explicit product goal establishes a mandate. |
| `mandate-gated` | The mandate status is `conditional` or `unproven`. | Keep the candidate out of implementation until the named product decision exists. |
| `delivered-equivalent` | A proven mandate exists and the canonical implementation already provides the required behavior for the evidenced window. | Close duplicate implementation work. Record only any narrower authority or evidence limitation. |
| `authority-gated` | A proven mandate and genuine canonical gap exist, but official authority does not cover the exact candidate window. | Wait for, acquire, or register exact-window authority. Never extrapolate another window. |
| `evidence-gated` | Mandate, exact authority, and a canonical gap are proven, but the required real golden payload or sanitized filed specimen is unavailable. | Wait for the named real artefact. Schema-only tests cannot clear this disposition. |
| `implementation-admitted` | All four gate booleans are true. | Permit a successor plan limited to reviewed registry data and real-behavior coverage through the canonical engine. |

### Candidate evidence-field contract

Each candidate is one surface and one applicability window. Do not combine an
outbound file, submitted file, declaration PDF, regime variant, or distinct
authority window in one record.

| Field | Required content |
|---|---|
| Candidate | Modelo, surface, regime or event when applicable, and the exact filing or revision window under review. |
| Mandate | `proven`, `conditional`, `unproven`, or `absent`; cite the accepted decision or explicit product goal and state the required behavior. Source availability is not a mandate. |
| Exact authority window | Official source identifier, registry revision, regime or event, inclusive start, inclusive end or open end, and whether the source covers that exact window. |
| Canonical implementation state | `delivered` or `gap`; name the canonical authority, renderer, parser, or archive path inspected and the real test evidence for the state. An absent layout does not prove a missing engine. |
| Real evidence or specimen | Evidence kind, identifier, evidenced window, and `available`, `missing`, or `not-required`. Export claims require a real golden payload; declaration-PDF claims require sanitized filed bytes. |
| Retirement | Boolean plus the accepted retirement or supersession basis. Keep this separate from evidence availability. |
| Evidence block | Boolean plus the exact missing golden payload, filed specimen, or other real artefact. Keep this separate from retirement and authority coverage. |
| Four-condition gate | Record `mandate_met`, `exact_authority_met`, `canonical_gap_met`, and `eligible_met` as explicit booleans. `eligible_met` is true only when the candidate is neither retired nor evidence-blocked. |
| Gate result | `pass` only when all four booleans are true; otherwise `fail`. Missing proof is false, not unknown or assumed. |
| Disposition | One taxonomy value selected by the precedence table. Do not embed the next action in this field. |
| Next action | One bounded action, named external prerequisite, or `none`. It must not authorize production work when the gate result is `fail`. |

The four-condition gate is authoritative:

1. `mandate_met`: an accepted decision or explicit current product goal requires the capability.
2. `exact_authority_met`: official authority covers the exact revision, event, regime, and filing window.
3. `canonical_gap_met`: the required capability is absent from the canonical current implementation, not merely absent from optional registry data.
4. `eligible_met`: the candidate is neither retired nor blocked on unavailable real evidence.

A source, application link, parity reference, unchecked legacy row, or absent
layout cannot make a gate true. Any admitted implementation adds reviewed
registry data and real-behavior coverage only. It must not add per-Modelo
renderers, submitted-file parsers, declaration-PDF parsers, registry
authorities, schema stores, or archive formats.

## Canonical implementation map

| Concern | Canonical implementation | Verification anchors | Boundary |
|---|---|---|---|
| Registry authority | `ValidatedRegistryAuthority` in `src/cadrumo/domain/calculations/registry/_authority.py:36`; `StaticModeloRepository._resolve_authority` in `src/cadrumo/core/resources/_repos/modelos.py:38` | Registry authority and corpus tests under `src/cadrumo/domain/calculations/registry/tests/` | There is one authority. `StaticModeloRepository.authority` is a thin faÃƒÂ§ade. |
| Runtime schema provider | `build_runtime_schema_provider` in `src/cadrumo/application/filing/runtime.py:359`; cached helper at `:409` and `ValidatedRegistryAuthority.load(...)` at `:417` | Runtime filing tests exercise the typed `RegistrySchemaAccessor` projection | The provider projects the canonical snapshot; it must not become an independent schema store. |
| Export layout resolution | `resolve_export_layout` in `src/cadrumo/domain/calculations/registry/_export.py:50` | Layout contract checks in `src/cadrumo/domain/calculations/registry/tests/test_registry_schema_part2.py:700` | Layouts are registry data selected for an applicable revision. |
| Export rendering and verification | `export_draft` in `src/cadrumo/application/filing/_export.py:278`, `_render_export_layout` at `:514`, `_render_record` at `:645`, and `_render_field` at `:699` | Real round trips and mutation detection in `src/cadrumo/application/filing/tests/test_fichero_boe_export_roundtrip.py` | The renderer is generic. A missing layout is not grounds for a new renderer. |
| Submitted-file parsing | `parse_export_payload` in `src/cadrumo/domain/calculations/registry/_export_parse.py:65`; observation routing in `src/cadrumo/adapters/outbound/aeat/sede/_declarations_observations.py:186` | `verify_export` in `src/cadrumo/application/filing/_export.py:391` and the fichero BOE round-trip test | The parser consumes the same registry layout as the renderer. |
| Declaration-PDF parsing | `parse_declaracion_bytes` and profile selection in `src/cadrumo/adapters/inbound/declaracion/_parser.py:158` and `:454` | `src/cadrumo/adapters/inbound/tests/test_extraction_parser_paths_resolve.py`; `src/cadrumo/adapters/inbound/declaracion/tests/test_parser_boundary_m130.py`; corpus gates in `src/cadrumo/domain/calculations/registry/tests/test_corpus_round_trip_gate.py:169` | Profiles are registry data. Selection must resolve exactly one applicable profile and hard-fail otherwise. |
| Live declaration observation | Submitted-file-first routing with PDF fallback in `src/cadrumo/adapters/outbound/aeat/sede/_declarations.py:936`; generic PDF call at `src/cadrumo/adapters/outbound/aeat/sede/_declarations_observations.py:407` | Adapter tests assert the actual observation paths | Submitted files and PDFs are two evidence formats routed to the corresponding generic parser. |
| Sealed archive persistence | `write_sealed_archive` in `src/cadrumo/adapters/persistence/storage/bucket/_sealed_archive_writer.py`; `read_sealed_archive` in `src/cadrumo/adapters/persistence/storage/bucket/_sealed_archive_reader.py` | Real archive round trips and rejection cases in `src/cadrumo/adapters/persistence/storage/bucket/tests/test_sealed_archive_roundtrip.py:52` | This is a local encrypted envelope with optional recovery material, not a declaration or AEAT fichero engine. |

The accepted registry-authority, declaration-extraction, and fichero-BOE decisions converge on the same architecture: reviewed registry data feeds shared engines. The sealed archive remains a distinct persistence service. None of these areas requires a duplicate code path.

## Export-layout adjudication register

| Modelo | Mandate or goal | Applicable authority and window | Current state | Disposition |
|---|---|---|---|---|
| 036 | The current accepted product scope is censo applicability, observation, and recording a declaration already filed by the operator; it does not mandate a Cadrumo M036 artifact. | The definitive v43 XLSX authority applies from 2025-02-03; provisional v42 must not ground the current revision. | Censo linkage and parity evidence exist; no M036 export layout or producer lifecycle is shipped. | **Not-mandated current product scope.** Treat as terminal product-scope, not an authorable layout gap. Reopen only through an accepted scope-expansion ADR, then re-evaluate all four conditions. |
| 037 | Accepted design retains 037 only as historical context after its suppression in favour of 036. | No active registry revision or record-design artefact; suppressed from 2025-02-03. | No active registry and no export layout. | **Retired.** Remove or refuse active entry points; do not author a layout. |
| 184 | Legacy goal requires export/file generation only where official filing support requires it. | `aeat-dr-184-2025`, PDF record design, from 2025-01-01; registry revision currently starts in 2015. | Filing link and parity reference exist; no layout. | **Conditional current gap, 2025+ only.** Decide whether local fichero generation is a product feature before work. |
| 190 | Legacy discovery and export-routing wording identify a possible outbound surface. | The registered 2025 PDF applies from 2025-01-01; bundled 2024 authority exists, and the accepted extraction ADR records the 2024 and 2025 EDI layouts as structurally identical under the current `2024-y-siguientes` revision. | Filing link and parity reference exist; no layout. | **Source-window-reconciliation-first, conditional candidate.** Confirm the product mandate and catalogue the 2024 source without splitting the revision unless a future official design diverges. |
| 193 | Legacy discovery and export-routing wording identify a possible outbound surface. | The registered 2025 PDF applies from 2025-01-01; bundled 2024 artefacts are not yet registered against a separate 2024 window. | Filing link and parity reference exist; no layout. | **Temporal-reconciliation-first, conditional candidate.** Confirm the product mandate and split 2024 from 2025 before implementation. |
| 308 | Legacy goal asks for deeper layout support only where required. | `aeat-dr-308-2019`, XLS record design, from 2019; current revision starts in 2009. | Filing link and parity reference exist; no layout. | **Conditional current gap, 2019+ only.** Decide the product requirement first; do not infer 2009-2018. |
| 309 | No accepted or legacy export-layout task exists. | `aeat-dr-309-2023`, XLS record design, from 2023; current revision starts in 2004. | Filing link and parity reference exist; no layout. | **Not mandated.** Source availability does not create a requirement. |
| 322 | Legacy goal asks for export/file layout only where required. | `aeat-dr-322-2026`, XLSX record design, from 2026; current revision starts in 2008. | Filing link and parity reference exist; no layout. | **Conditional current gap, 2026+ only.** Product decision first; no historical extrapolation. |
| 347 | Legacy work explicitly deferred record bindings until the official PDF designs could be transcribed. | Registered PDF authorities cover 2011-12-13 through 2024-12-31 and 2025+; current revision starts in 2008. | Filing link and parity references exist; no layout. | **Windowed conditional candidate.** Confirm the product mandate; register the 2008-to-2010 windows or limit any later support. |
| 353 | Legacy goal asks for export/file layout only where required. | `aeat-dr-353-2026`, XLSX record design, from 2026; current revision starts in 2008. | Filing link and parity reference exist; no layout. | **Conditional current gap, 2026+ only.** Product decision first; no historical extrapolation. |
| 360 | No accepted or legacy export-layout task exists. | `aeat-dr-360-2010`, PDF record design, from 2010-04-01, aligned with the revision. | Filing link and parity reference exist; no layout. | **Not mandated.** A feasible format is not a product requirement. |
| 369 | Legacy discovery and export-routing wording identify a possible outbound surface. | `aeat-dr-369-2021`, XLSX record design, from 2021-07-01, aligned with three separate Union, Importacion, and Exterior revision variants. | Three filing links and parity references exist; no layouts. | **Conditional candidate with mandatory regime separation.** Confirm the product mandate and never flatten the three variants into one assumed schema. |
| 840 | Legacy wording explicitly identifies missing layout-binding rows, but does not establish a current product mandate. | `aeat-dr-840`, PDF record design, from 2003-09-19, aligned with the revision. | Filing link and parity reference exist; no layout. | **Explicit but conditional data candidate.** Confirm machine-file generation as product scope before transcribing registry fields and bindings. |

Every active candidate currently has zero export layouts. That observation is implementation state, not a mandate. The generic exporter already refuses revisions without a selected layout at `src/cadrumo/application/filing/_export.py:319` and reports unsupported or non-renderable layouts through the guard ending at `:365`; these are correct safety boundaries.

## Declaration-extraction adjudication register

| Modelo | Mandate or goal | Applicable authority and window | Current state | Disposition |
|---|---|---|---|---|
| 037 | Accepted design requires historical retirement, not extraction support. | No active registry revision or filed evidence window. | No extraction profile; no active registry. | **Retired.** Do not add a profile. |
| 200 | Reconciliation needs observations from available declaration evidence. | The registered `modelo-200-fichero-boe` layout is sourced by `aeat-dr-200-2025` for 2025; the current revision begins in 2024. No filed declaration-PDF specimen is bundled. | The submitted-file route already resolves the registry layout and uses `parse_export_payload`; no PDF profile exists. | **Submitted file: delivered-equivalent for 2025. Declaration PDF: evidence-gated.** Do not claim 2024 coverage or PDF support from the 2025 layout. |
| 308 | Legacy goal requires real declaration evidence before an extraction profile is accepted. | Registered record-design source begins in 2019; the revision begins in 2009. No filed declaration specimen is bundled. | Generic extractor link exists; no profile. | **Evidence-gated.** A record design is not a filed declaration PDF. |
| 309 | Legacy goal requires real declaration evidence before an extraction profile is accepted. | Registered record-design source begins in 2023; the revision begins in 2004. No filed declaration specimen is bundled. | Generic extractor link exists; no profile. | **Evidence-gated.** Do not derive a PDF profile from the record design. |
| 322 | Legacy goal requires real declaration evidence before an extraction profile is accepted. | Registered record-design source begins in 2026; the revision begins in 2008. No filed declaration specimen is bundled. | Generic extractor link exists; no profile. | **Evidence-gated.** Limit any future profile to evidenced windows. |
| 353 | Legacy goal requires real declaration evidence before an extraction profile is accepted. | Registered record-design source begins in 2026; the revision begins in 2008. No filed declaration specimen is bundled. | Generic extractor link exists; no profile. | **Evidence-gated.** Limit any future profile to evidenced windows. |
| 360 | Legacy goal requires real declaration evidence before an extraction profile is accepted. | Record-design authority and revision align from 2010-04-01, but no filed declaration specimen is bundled. | Generic extractor link exists; no profile. | **Evidence-gated.** Alignment of a record design does not prove declaration-PDF geometry. |

The reconciliation service currently enrols only Modelos 100, 111, 130, 190, 303, and 390 in `src/cadrumo/application/modelo/_reconcile.py:66`. This is current scope, not permission to manufacture profiles for the remaining candidates. A candidate becomes implementable only when a real artefact supports deterministic field coordinates, applicability, and a real-behavior corpus test.

## Modelo 100 exercise-2026 time gate

Modelo 100 registry revisions and applicable sources currently stop at exercise 2025 under `src/cadrumo/_data/registry/aeat/modelos/100/revisions/`. Exercise 2026 is therefore time-gated until the official AEAT or BOE authority for that exercise is published, acquired, verified, and bundled. The 2025 revision, layout, coordinates, and legal source must not be rolled forward by assumption.

## Forward implementation contract

Any later implementation arising from this adjudication must satisfy all of the following:

- establish a mandate before treating an absent layout or profile as backlog;
- register applicable legal and artefact provenance for the exact revision window;
- add reviewed registry data to the existing authority rather than another provider or schema store;
- exercise the existing generic renderer/parser with real golden payloads and mutation-sensitive round trips;
- exercise the existing generic declaration parser with real filed PDF bytes and corpus expectations;
- keep the sealed archive service separate from AEAT export and declaration formats;
- refuse ambiguous, unsupported, or out-of-window resolution instead of silently extrapolating; and
- add no Modelo-specific renderer, submitted-file parser, or declaration-PDF parser.
