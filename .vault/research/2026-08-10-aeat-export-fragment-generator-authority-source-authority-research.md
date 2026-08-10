---
tags:
  - '#research'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:919357bb74ba61e894c2274b8f7fc5d7d54fa4a970f870a7190d581ff62bb55b'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-export-fragment-generator-adr]]"
  - "[[2026-08-09-aeat-design-relayout-boundary-modelo-200-fragment-tree-provenance-research]]"
---
# `aeat-export-fragment-generator-authority` research: `source authority`

The relayout campaign needs a mechanism that can establish AEAT layout fidelity, not merely preserve the behavior of a shipped tree. The evidence shows that re-coordinating from an existing tree cannot meet that standard. The viable authority split is an exact official binary for coordinates plus an independently reviewed semantic map for registry meaning, with refusal wherever the two cannot be joined bijectively.

## Findings

### The shipped tree is not an AEAT-grounded oracle

`2026-08-09-aeat-design-relayout-boundary-modelo-200-fragment-tree-provenance-research` establishes that Modelo 200's tree was hand/agent-transcribed, has no per-field source anchors, and has only internally consistent registry links. The current relayout plan's S77 measurement found only 2,402 of 6,537 fields externally matchable without ambiguity. Re-coordination therefore preserves an unverified mapping and cannot prove correctness against AEAT.

### The typed record-design parser is the coordinate authority

The shipped record-design extractors return typed sheets and fields from the exact bundled official binary. Their output owns record membership, source order, offsets, lengths, AEAT type, validation/content metadata, and declared totals. Derived `.extracted.md` and `.extracted.json` files are review aids and cannot become generator inputs because that would insert a second, mutable transcription layer.

### Registry semantics require a separate authored authority

The official designs do not carry Cadrumo's `kind`, canonical `casilla_id`, `header_key`, `draft_attribute`, or legal references. Those values require an authored, per-modelo and per-design semantic map keyed by exact parser anchors: sheet, source row or cell, ordinal, and parsed slot identity. A mapping keyed by neighbouring tree position, fuzzy descriptions, or index alignment would recreate the ambiguity already measured by S77.

### Provenance and atomicity are part of correctness

The current trees bulk-stamp design references and do not preserve a field-level derivation chain. A generated revision needs an adjacent non-loader provenance manifest recording the exact source reference and SHA-256, parser and generator schema versions, semantic-map digest, target revision, normalized loader-semantic digest, and output file digests. Generation must refuse the whole revision on missing, duplicate, or ambiguous mappings and publish only after complete parse, validation, and comparison.

### The mechanism must be proven by adversarial gates

Positive generation alone cannot distinguish a correctly mapped tree from a plausible one. Required proof includes parser completeness, mapping bijection and canonical-reference validation, source applicability and hash checks, deterministic double generation, repository `--check`, extent/overlap and full-load gates, emitted-byte proofs across revision splits, and mutation failures for coordinate drift, missing or duplicate mapping, source hash drift, output tampering, partial trees, illegal exceptions, and target-revision mismatch.

### Architecture authority

The delegated Sol medium architecture review concluded that the accepted re-coordination ADR must be superseded and that this mechanism must land as a separate prerequisite before the held relayout waves resume. That ruling resolves the option choice; this record preserves the evidence boundary supporting it.

## Sources

- `2026-08-08-aeat-design-relayout-boundary-export-fragment-generator-adr`
- `2026-08-09-aeat-design-relayout-boundary-modelo-200-fragment-tree-provenance-research`
- `2026-08-08-aeat-design-relayout-boundary-plan`, steps W01.P02.S77-S80
- `src/cadrumo/domain/calculations/registry/_record_design.py`
- `src/cadrumo/domain/calculations/registry/_export.py`
- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/`
