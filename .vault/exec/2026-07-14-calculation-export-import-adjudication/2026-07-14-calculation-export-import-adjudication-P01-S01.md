---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S01'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---
# Reconfirm the canonical registry, export renderer/parser, declaration parser, and sealed-archive boundaries against current source and tests

## Scope

- `src/cadrumo/`
- `.vault/reference/`

## Description

Reconciled the accepted ADR, research note, reference, and plan against the current implementation before authorizing any feature work. The earlier semantic-RAG attempt timed out without returning usable evidence, so this step used the plan's approved exact-source fallback rather than treating the timeout as proof of missing code.

The inspection was bounded to the named production boundaries and their real-behaviour test anchors. The principal symbol lookup was:

```text
rg -n "^(class ValidatedRegistryAuthority|def resolve_export_layout|def parse_export_payload|def export_draft|def parse_declaracion_bytes|def write_sealed_archive|def read_sealed_archive)\b" src/cadrumo
```

The resulting definitions and direct call paths were read in:

- `src/cadrumo/domain/calculations/registry/_authority.py`
- `src/cadrumo/domain/calculations/registry/_export.py`
- `src/cadrumo/domain/calculations/registry/_export_parse.py`
- `src/cadrumo/application/filing/_export.py`
- `src/cadrumo/adapters/inbound/declaracion/_parser.py`
- `src/cadrumo/adapters/persistence/storage/bucket/_sealed_archive_writer.py`
- `src/cadrumo/adapters/persistence/storage/bucket/_sealed_archive_reader.py`

The corresponding test anchors were inspected in:

- `src/cadrumo/domain/calculations/registry/tests/test_authority.py`
- `src/cadrumo/domain/calculations/registry/tests/test_committed_registry.py`
- `src/cadrumo/application/filing/tests/test_fichero_boe_export_roundtrip.py`
- `src/cadrumo/domain/calculations/registry/tests/test_registry_schema_part2.py`
- `src/cadrumo/adapters/inbound/tests/test_extraction_parser_paths_resolve.py`
- `src/cadrumo/adapters/inbound/declaracion/tests/test_parser_boundary_m130.py`
- `src/cadrumo/domain/calculations/registry/tests/test_corpus_round_trip_gate.py`
- `src/cadrumo/adapters/persistence/storage/bucket/tests/test_sealed_archive_roundtrip.py`

## Outcome

- `ValidatedRegistryAuthority` is the existing validated, cached registry access boundary. Its `load` and `bundled_authority` paths construct authority from the committed registry tree; no competing authority loader is required.
- `resolve_export_layout` validates and selects the registry-declared export layout, while `parse_export_payload` consumes that resolved layout. `export_draft` already renders through the generic layout/record/field helpers, and the fichero BOE round-trip tests exercise the real renderer and parser rather than mirrored test logic.
- `parse_declaracion_bytes` already loads `ValidatedRegistryAuthority` and selects a registry extraction profile. The implementation explicitly makes registry data, not per-model Python classes, select declaration parsing behaviour.
- `write_sealed_archive` and `read_sealed_archive` are the strict local `.cadrumo-bucket.tar.gz` persistence boundary. They are deliberately separate from AEAT export layouts and declaration ingestion, and their round-trip tests invoke the real writer and reader.
- No factual mismatch was found between the accepted architecture documents and these source boundaries. This is genuine reconciliation work, not missing production implementation; no production code, tests, or reference content were changed.

## Notes

- The prior semantic-RAG timeout is recorded as a tooling limitation, not as negative implementation evidence. Exact source and direct real-test inspection supplied the grounding for this step.
- No duplicate renderer, parser, authority, declaration adapter, or sealed-archive path is authorized by this finding.
- The P01.S01 plan checkbox remains open pending the parent execution workflow's review and closure actions. Nothing was staged or committed in this step.
