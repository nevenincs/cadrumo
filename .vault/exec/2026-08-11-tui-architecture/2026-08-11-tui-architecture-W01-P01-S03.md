---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:7927fbe834fdfa11fa300af425a6c023bde9a248452f325b5daa506aa8b8593d'
step_id: 'S03'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Reject static, dynamic, type-only, re-export, registration, Textual-location, and private-facade bypasses

## Scope

- `src/cadrumo/tests/test_import_hygiene_gate.py`

## Description

- Ground every bypass family in D11 and semantic RAG before extending the canonical import-hygiene scanner.
- Consolidate the canonical TUI package name and add one AST boundary result model rather than parsing imports again in the test.
- Join permitted legacy Textual locations to the accepted S01 migration census and the two ruled legacy package roots.
- Exercise static, type-only, re-export, dynamic, annotation, registration, Textual-location, and static/dynamic private-facade failures with real temporary modules.

## Outcome

`dev.quality.import_hygiene_scan` now owns the missing D11 AST boundary alongside its existing static import, dynamic import, facade, and migration authorities. Outside callers cannot import, type-annotate, dynamically load, re-export, or register the dedicated TUI. Textual imports must live under the canonical TUI root, except for exact `(consumer module, Textual target)` edges bound by accepted digest `ff45a174acd6c53d0f6265770462d9b28b65b03dd72127f8a9e64de0a63b7ebe`. Canonical TUI modules cannot reach cross-package private implementation modules through direct private modules, private names imported through public facades, or dynamic imports.

The scanner reuses `walk_module_imports`, `iter_dynamic_import_targets`, `owning_package`, and the S01 manifest rather than mirroring their semantics in pytest. Expression annotations resolve imported aliases and complete attribute chains. Registration detection follows TUI object or literal references crossing any call boundary, independent of the callee name; `registry.add(...)` is a proved rejected shape. The existing Family 1 gate remains the general static private-facade authority; S03 adds only the dynamic and TUI-specific projections it did not cover.

Focused verification:

    uv run --no-sync pytest -q -n 0 src/cadrumo/tests/test_import_hygiene_gate.py -k "tui_boundary or accepted_textual_consumer"
    16 passed, 19 deselected in 170.46s

    uv run --no-sync ruff check dev/quality/import_hygiene_scan.py src/cadrumo/tests/test_import_hygiene_gate.py
    All checks passed!

    uvx vaultspec-core vault check all
    Exit code: 0 in 57.2s
    Vault Check - All: all hard dimensions clean; 1297 shared warnings (1 orphan, 4 features, 53 exec-mapping, 1207 body-sections, 29 schema, 3 modified-stamp). The three modified-stamp warnings named this S03 exec, its independent review audit, and a peer canonical-identifiers exec; they are attestation warnings rather than structural failures.

## Notes

S03 remains open and uncommitted pending independent review. No broad gate was run. Review remediation added mutation-sensitive proofs for public-facade private names, aliased expression annotations, arbitrary registrar method and object-reference shapes, new Textual files planted under both legacy implementation and development roots, and an accepted consumer adding a second unaccepted Textual target. The edge digest covers all current source and runtime development-tool Textual edges; changing a target or adding an edge now refuses rather than riding an importer/module exemption. W06.P15.S91 owns removing the accepted legacy edges and proving final hard zero.
