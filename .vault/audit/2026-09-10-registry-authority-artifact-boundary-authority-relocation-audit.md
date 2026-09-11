---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:a5dc5a4de339605faf08bcce3a8716594b6c3e3163ffc78e33fe1a238edfdfe6'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---

# `registry-authority-artifact-boundary` audit: `authority relocation`

## Scope

Reviewed the W03.P04.S06 runtime/development boundary against the accepted immutable-publication decision. The review traced runtime authority construction, corpus/provenance access, development compiler ownership, and registry-local test fixtures. It deliberately treated outcomes from artifact and workflow behavior as gate evidence, and did not use AST, text-shape, or source-inventory assertions as acceptance tests.

## Findings

### authority-relocation | high | Runtime package retains a mutable normative-corpus resolver

`corpus_provenance.resolve_normative_corpus_path` and `classify_normative_corpus_provenance` remain under the runtime package and accept a source root, resolve a normative corpus target, and read its bytes. The development publisher and legal-grounding compiler invoke that path. This contradicts the ADR consequence that source-evidence parsing remains a development dependency and leaves a production-importable raw-root capability even though the published-evidence path is otherwise artifact-backed. The byte-only classification and the `NormativeCorpusProvenance` value vocabulary can remain at the typed runtime boundary if needed; path resolution and source-byte reads must move to the development compiler or publisher.

### authority-relocation | high | Registry-local pytest fixtures still compile mutable bundled sources

The registry test `conftest.py` still calls `bundled_registry_tree()` and builds snapshots with `source_root=bundled_path()`. Numerous tests below the runtime registry test tree consume that fixture or call the same helper directly. Those are authoring/compiler tests co-located with runtime tests, so an installed-package boundary would either omit their dependency or retain raw authoring inputs to run them. They must move with their support fixtures to `dev/registry/tests`, while runtime tests should exercise `bundled_authority()` and signed artifact projections only.

### authority-relocation | high | A remaining runtime-tree test imports a deleted authoring compiler module

`test_export_projection_refs.py` remains below the runtime registry tests but imports the relocated `_loader_internals` module. Its focused collection fails with `ModuleNotFoundError`; this is a concrete incomplete relocation rather than a theoretical import-shape concern. The test contains compiler hydration behavior and belongs with the development compiler tests. The artifact contract suite itself passes 18 focused behavioral tests, so the failure is localized to the incomplete test move rather than artifact decoding.

## Recommendations

- Address the mutable-corpus-resolver finding by relocating source-root resolution and corpus-byte classification entrypoints to development tooling; keep runtime provenance queries limited to the signed evidence projection.

- Finish the registry-test relocation as an atomic move: move the local `conftest.py`, its `bundled_registry_tree`/`build_snapshot` dependants, and the projection-loader tests to development ownership, updating direct imports rather than creating compatibility shims.

- Re-run the moved compiler tests against a temporary candidate corpus plus the existing artifact contract and source-free workflow tests. These should prove compilation/publication refusal and artifact-only runtime behavior through real calls; do not replace them with AST, static, or source-string assertions.
