---
tags:
  - "#adr"
  - "#aeat-export-fragment-generator-authority"
date: '2026-08-10'
related:
  - '[[2026-08-08-aeat-design-relayout-boundary-export-fragment-generator-adr]]'
  - '[[2026-08-09-aeat-design-relayout-boundary-modelo-200-fragment-tree-provenance-research]]'
  - '[[2026-08-10-aeat-export-fragment-generator-authority-source-authority-research]]'
  - '[[2026-08-10-aeat-export-fragment-generator-authority-s08-authority-gap-research]]'
  - '[[2026-08-11-aeat-export-fragment-generator-authority-s54-sector-source-taxonomy-research]]'
  - '[[2026-08-11-aeat-export-fragment-generator-authority-s61-dp30300-envelope-authority-research]]'
supersedes:
  - '2026-08-08-aeat-design-relayout-boundary-export-fragment-generator-adr'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:05ffe61ac2974f38de47b42e69ec6d53d3678040037b2fb53376f4bd5edc53e0'
---
# `aeat-export-fragment-generator-authority` adr: `official-binary coordinates, reviewed render profiles, and semantic maps generate export fragments` | (**status:** `accepted`)

## Problem Statement

The accepted official-binary and semantic-map split leaves some wire facts unauthorised when the exact workbook field anchor carries no usable content, and it does not classify variable composition wrappers. The generator needs one exhaustive reviewed authority for those absent wire facts and an explicit boundary between fixed-width records and variable envelopes before real-target generation can resume.

## Considerations

- The original coordinate-versus-meaning authority split is grounded by `2026-08-10-aeat-export-fragment-generator-authority-source-authority-research`.
- The unresolved fixed-width totals, absent wire facts, and variable-wrapper boundary are grounded by `2026-08-10-aeat-export-fragment-generator-authority-s08-authority-gap-research`.
- The real-target completeness and refusal requirements are recorded by `2026-08-10-aeat-export-fragment-generator-authority-s08-independent-review-audit`.
- Export fragments are filing-correctness inputs, so partial coverage, implicit defaults, conflicting authorities, and guessed output are unacceptable.
- Revision selection and applicability remain authored registry decisions governed by the parent relayout ADR; this decision does not infer revision boundaries.

## Considered options

- **Keep refusing every design with absent field-level wire facts. Rejected as the permanent model.** It is safe but prevents reviewed source-scoped conventions from completing an otherwise authoritative design.
- **Put wire formatting in the semantic map. Rejected.** It mixes registry meaning with source wire representation and creates a second coordinate-adjacent authority.
- **Infer formats from AEAT type and width or from a neighbouring tree. Rejected.** Defaults and legacy-tree oracles turn incomplete evidence into silent filing behavior.
- **Use an exhaustive source-SHA-pinned per-design render profile. Chosen.** It provides one reviewed home for wire facts absent at exact workbook field anchors while leaving official coordinates and registry meaning in their existing authorities.
- **Treat variable wrappers as fixed records with inferred totals. Rejected.** It truncates composition semantics and falsely converts a variable envelope into a fixed-width record.

## Constraints

- The exact bundled official binary, selected through the source catalogue and verified by SHA-256, is the sole coordinate input.
- The shipped typed record-design parser output is consumed directly; derived extraction files are never inputs.
- The parser may recover official integer totals expressed by the source's `Total:` label and must prove them against terminal extent. It never invents a total, content value, coordinate, or wire interpretation.
- A separate per-modelo, per-design semantic map supplies only registry meaning and is keyed by exact source anchors. Renderer formatting and transport interpretation never enter semantic-map entries. The join is bijective and refuses the entire design on missing, duplicate, fuzzy, or ambiguous matches.
- One exhaustive per-design render profile, bound to the exact source SHA-256, is the sole reviewed authority for wire facts absent at their exact workbook field anchors. It may not override or conflict with wire facts present in the official source.
- Every profile rule resolves to exact source anchors. Coverage must be complete for every otherwise-unrenderable field, including all 126 smaller-width fields; group conventions require an explicit reviewed membership set rather than type-and-width inference.
- Profiles distinguish unsigned `Num` handling from signed `N` handling and define the sign representation explicitly. No numeric, decimal, date, flag, identifier, digit-string, or literal default is implicit.
- Missing anchors, uncovered fields, duplicate or overlapping rules, conflicts with official content, inapplicable design identity, or source-hash drift refuse the whole design before output.
- `DP200000` is a typed variable envelope and composition wrapper outside fixed-width record generation. It is never truncated to its fixed prefix, assigned an inferred fixed total, or emitted as a fixed record; its envelope and composition behavior must be modeled separately and proven before any generation for that design.
- `DP30300` is likewise a typed variable envelope, not a fixed record and not part of the fixed-record semantic-map entry set. Its thirteen prefix anchors, Variable body, relative eighteen-byte closer, and derived total form one source-hash-bound composition contract shared across the five explicit Modelo 303 epochs.
- The four-byte AEAT program identifier and nine-byte software-developer tax identifier are one typed product/software identity authority. They are not filing producers, presenter or taxpayer identities, generic headers, guessed literals, or defaults. Generation refuses until explicit product authority supplies both values.
- The envelope definition declares exact prefix-anchor semantics, ordered body record identities, closer reuse of modelo, discriminant, year, period, and record-type semantics, and total-length derivation. Provenance carries the envelope schema and digest, source hash, prefix derivations, ordered member digests, product-authority evidence, closer derivation, and total.
- Neighbouring fragment trees are neither inputs nor correctness oracles. Legacy trees are explicitly unverified bootstrap evidence and may not supply profile rules or defaults.
- Generated replacements are a hard cutover: superseded manual fragment trees, single-file/direct-revision compatibility loaders, derivative record-design fallbacks, and print-only unmeasured paths are deleted. No legacy fallback, migration support, or silent green result remains.
- Typed, hash-pinned exceptions may describe parser or source anomalies but may never supply coordinates, bypass mapping bijection, override official content, or substitute for exhaustive render-profile coverage.
- Generated TOML and provenance are CLI-owned and never hand-edited.
- One invocation targets one authored revision/design pair; revision splitting, renames, and migration remain explicit outside the generator.
- User-profile `export_headers` metadata and export-only `filing_export.*` paths are legacy producer redeclarations and are deleted, not migrated or aliased. Registry export meaning reaches the renderer only through canonical typed owners and the filing producer snapshot.
- Modelo 100 filing modality is a semantic carve-out rather than an export producer: its sole persisted home is `renta_filing.declaration_type`, typed by the public core `RentaDeclaracionType`. Bindings, questions, setup, wizard, calculation, comparator, and XML projection consume that one axis directly; `FilingProducerKey` does not duplicate it.
- The rental reduction tier is not export metadata. Its canonical profile home is `renta_rental.reduccion_art_23_2_tier_2024`, retaining its existing enum and legal grounding.
- Old profile paths, old enum import paths, fallback reads, aliases, silent migration, and re-entry through generic profile facts are hard failures.

## Implementation

Build the development-only generator under `dev/registry/`. It parses the selected official binary into an intermediate representation retaining source reference and hash, workbook format, sheet, source row or cell anchor, ordinal, record identity, offset, length, AEAT type, normalized description, validation/content metadata, declared total, and typed record kind.

Normalize official `Total:` integers without synthesizing absent values. Represent variable envelopes separately from fixed-width records, and block target generation until their composition contract has passed dedicated structural and byte-level proof.

For Modelo 303, render the typed DP30300 envelope as exact prefix fields, followed by the ordered rendered body records, followed by the derived relative closer. Derive and prove the Variable total from emitted bytes. Refuse malformed, incomplete, reordered, duplicate, source-drifted, or product-authority-incomplete envelopes before any target mutation; remove the blanket renderer refusal only when those structural and byte-level proofs pass.

Join fixed-width source fields to the reviewed semantic map, then resolve only absent wire facts through the exhaustive render profile for the exact design and source hash. Validate source applicability, complete semantic bijection, exact-anchor profile coverage, rule consistency, explicit `Num` and signed-`N` behavior, and agreement with every present official content value before rendering.

Generate the entire target revision's `export/` tree plus an adjacent non-loader provenance manifest. The manifest records source, semantic-map, and render-profile digests; parser, profile, and generator schema versions; target revision; normalized loader-semantic digest; and file digests.

Generate into a temporary target, load and validate it completely, compare normalized semantics and provenance, and swap atomically. `--check` regenerates independently and refuses semantic, profile, provenance, or exact generated drift.

The profile-side cutover deletes the `export_headers` selector taxonomy and export-only `filing_export.*` fields. It atomically retargets every Renta modality consumer to `renta_filing.declaration_type`, relocates `RentaDeclaracionType` to the core public facade without an old-path re-export, and retargets the rental reduction tier to `renta_rental.reduccion_art_23_2_tier_2024`. Tests reject every removed path and import surface.

The gate suite covers parser completeness, official-total recovery, fixed-record geometry, variable-envelope classification and composition, canonical-reference validity, mapping bijection, exhaustive profile coverage, `Num` versus signed-`N` encoding, all 126 smaller-field rules, applicability, deterministic double generation, mutation failures, extent and overlap, complete registry load, repository drift, and real emitted bytes across representative revision boundaries.

## Rationale

The chosen profile is the narrowest extension that preserves the decisive split in `2026-08-10-aeat-export-fragment-generator-authority-source-authority-research`: the official design owns coordinates and present wire facts, the semantic map owns registry meaning, and a reviewed source-bound profile owns only wire facts the exact anchors omit. The authority gaps and variable-envelope classification in `2026-08-10-aeat-export-fragment-generator-authority-s08-authority-gap-research` rule out parser invention, type-and-width defaults, semantic-map expansion, and fixed-record truncation.

## Consequences

- `2026-08-08-aeat-design-relayout-boundary-export-fragment-generator-adr` remains superseded; this accepted record remains the single governing generator-authority decision.
- The generator remains a prerequisite to relayout steps that promise parsed, non-transcribed export trees; existing manual trees remain unverified until regenerated and proven.
- Render-profile changes become independently reviewable wire-authority changes and their digest becomes part of provenance and drift detection.
- Semantic maps remain reviewable meaning-only artifacts.
- Designs containing a variable envelope cannot generate fixed-width output until the separate envelope contract and composition proof pass.
- Source, parser, or profile corrections can produce large generated diffs, but exhaustive validation and deterministic checks make that drift explicit.
- Tests fail if generation reads legacy layout membership, applies a default to an uncovered anchor, conflates `Num` with signed `N`, leaves a smaller field ungrounded, accepts profile conflict or hash drift, truncates a variable envelope, or permits deleted compatibility surfaces to reappear.
- Renta calculation and question bindings retain their semantic modality axis independently of export layout support; deleting export producer redeclarations cannot delete or default personal-income-tax inputs.
