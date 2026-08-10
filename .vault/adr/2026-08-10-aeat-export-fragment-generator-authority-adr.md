---
tags:
  - "#adr"
  - "#aeat-export-fragment-generator-authority"
date: '2026-08-10'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-export-fragment-generator-adr]]"
  - "[[2026-08-09-aeat-design-relayout-boundary-modelo-200-fragment-tree-provenance-research]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-source-authority-research]]"
supersedes:
  - '2026-08-08-aeat-design-relayout-boundary-export-fragment-generator-adr'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:d262ba1dcb18aaf679879470e9ff95b7c768f69da3fe0b88c3fc03d74d3b8e42'
---
# `aeat-export-fragment-generator-authority` adr: `official-binary coordinates and explicit semantic maps generate export fragments` | (**status:** `accepted`)

## Problem Statement

The accepted re-coordination decision cannot establish AEAT correctness because its source tree is unverified and most fields cannot be paired unambiguously to the official design. The relayout campaign therefore needs a replacement authority model before it can generate revision-specific export trees.

## Considerations

- The provenance and match-rate boundary is established by `2026-08-09-aeat-design-relayout-boundary-modelo-200-fragment-tree-provenance-research` and W01.P02.S77.
- The official binary supplies layout coordinates but not Cadrumo registry semantics, as grounded by `2026-08-10-aeat-export-fragment-generator-authority-source-authority-research`.
- Export fragments are filing-correctness inputs, so partial or guessed output is unacceptable.
- Revision selection and applicability remain authored registry decisions governed by the parent relayout ADR; this decision does not infer revision boundaries.

## Considered options

- **Re-coordinate a neighbouring or existing tree. Rejected.** It preserves an unverified semantic-to-coordinate mapping and is blocked by measured ambiguity.
- **Generate directly from the official design alone. Rejected.** The design lacks registry semantics and legal/canonical identities.
- **Official binary plus explicit semantic map. Chosen.** It gives each authority only the facts it can establish and makes the join reviewable and fail-closed.
- **Hand-author generated TOML or permit positional exceptions. Rejected.** Both recreate unauditable transcription and silent drift.

## Constraints

- The exact bundled official binary, selected through the source catalogue and verified by SHA-256, is the sole coordinate input.
- The shipped typed record-design parser output is consumed directly; derived extraction files are never inputs.
- A separate per-modelo, per-design semantic map supplies only registry meaning and is keyed by exact source anchors. The join is bijective and refuses the entire design on missing, duplicate, fuzzy, or ambiguous matches.
- Neighbouring fragment trees are neither inputs nor correctness oracles. Legacy trees are explicitly unverified bootstrap evidence.
- Generated replacements are a hard cutover: superseded manual fragment trees, single-file/direct-revision compatibility loaders, derivative record-design fallbacks, and print-only unmeasured paths are deleted. No legacy fallback, migration support, or silent green result remains.
- Typed, hash-pinned exceptions may describe parser or source anomalies but may never supply coordinates or bypass mapping bijection.
- Generated TOML and provenance are CLI-owned and never hand-edited.
- One invocation targets one authored revision/design pair; revision splitting, renames, and migration remain explicit outside the generator.

## Implementation

Build a development-only generator under `dev/registry/`. It parses the selected official binary into an intermediate representation retaining source reference and hash, workbook format, sheet, source row or cell anchor, ordinal, record identity, offset, length, AEAT type, normalized description, validation/content metadata, and declared total.

Join that representation to the reviewed semantic map, validate source applicability and complete bijection, then generate the entire target revision's `export/` tree plus an adjacent non-loader provenance manifest. The manifest records source and map digests, parser/generator schema versions, target revision, normalized loader-semantic digest, and file digests.

Generate into a temporary target, load and validate it completely, compare the normalized semantics and provenance, and swap atomically. `--check` regenerates independently and refuses semantic or exact generated/provenance drift.

The gate suite covers parser completeness, canonical-reference validity, mapping bijection, applicability, deterministic double generation, mutation failures, extent/overlap, complete registry load, repository drift, and real emitted bytes across representative revision boundaries.

## Rationale

This split follows the decisive evidence in `2026-08-10-aeat-export-fragment-generator-authority-source-authority-research`: official designs can author coordinates, while registry semantics require an explicit human-reviewed authority. Making their join exact and fail-closed removes both the unverified-tree oracle and the temptation to guess from position.

## Consequences

- `2026-08-08-aeat-design-relayout-boundary-export-fragment-generator-adr` is superseded.
- The generator becomes a prerequisite to relayout steps that promise parsed, non-transcribed export trees; existing manual trees remain unverified until regenerated and proven.
- Every semantic-map change is reviewable independently from parser and coordinate changes.
- Source/parser corrections can produce large generated diffs, but provenance and deterministic checks make that drift explicit.
- The campaign gains a correctness proof against official designs, not merely regression agreement with current behavior.
- Tests fail if generator validation or generation reads legacy layout membership, if a required official design is unparseable or unmeasured, or if deleted compatibility surfaces reappear.
