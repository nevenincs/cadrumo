---
tags:
  - '#reference'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:e47b233955b0a86130e30a9943018eab5e9045f6e2049e1e870240f1bfaa9cc8'
related:
  - "[[2026-09-02-object-name-audit-implementation-review-audit]]"
  - "[[2026-07-01-import-centralization-adr]]"
---

# `object-name-declustering` reference: `repository integration surface`

This reference maps the existing Cadrumo analyzers and contracts that a safe declustering planner should compose. It is an implementation blueprint, not authorization to rename code.

## Summary

Its declaration model at lines 91-106 contains name, kind, path, line, visibility, test, and overload state. Collection at lines 196-255 enrolls Python modules under `src` and `dev`; analysis at lines 277-327 emits exact collisions and plural-looking names. JSON at lines 336-347 contains findings and summary, but not the full declaration census, stable IDs, import reach, content hashes, owners, or target proposals. Extending its output with stable locators is preferable to a second name scanner.

Semantic overlap evidence already lives in `dev/audit/semantic_duplication.py`. The module contract at lines 1-37 makes every fingerprint a candidate rather than a verdict. Relevant detectors are call fingerprints at 253-278, derivation fingerprints at 308-338, identical field sets at 341-371, import overlap at 374-405, and package overlap at 408-441. Its default is production-only and its parser currently skips syntax/encoding failures at 134-143, so it cannot serve as a fail-closed execution precondition without hardening.

Copy/paste evidence is owned by `dev/audit/duplication.py` and the `audit-duplication` recipe at `Justfile:875`. It wraps jscpd and should remain an advisory non-regression signal.

The scanner is strongest below `src/cadrumo` and does not provide a complete cross-repository reference graph, so the planner must state which reference classes were resolved and refuse unresolved dynamic sites.

`dev/registry/analysis/load_census.py:122` already constructs a Grimp graph with caching disabled to avoid stale mtime keys. That is the preferred import-edge authority. NetworkX 3.6.1 is present transitively at `uv.lock:1998`, but making it a direct dependency is an ADR decision. A minimal implementation can compute bipartite connected components without NetworkX if dependency ownership is undesirable.

It neither moves arbitrary public modules nor accepts a typed manifest, validates file hashes, emits a rehearsal receipt, or proves its changed-path set. Treat it as a catalogue of residue surfaces, not the new engine.

Generated API documentation is owned by `dev/docs/apidocs/manager.py:131` and its checks; module renames must invoke that generator rather than editing generated references. The accepted import-centralization decision requires one defining module, direct imports, exact dynamic targets, atomic test/tool/config moves, deletion of old paths, and no facades or compatibility shims.

The proposed planner should live beside development tooling, not in `src/cadrumo`. Its read-only `inventory` phase consumes object-name JSON, the full declaration census, Grimp edges, import-hygiene surfaces, semantic candidates, and clone evidence. Its reviewed manifest records stable operation/finding IDs, old and new qualified locators, disposition, owner, byte preconditions, advisory AST fingerprint, expected reference classes and changed paths, generators, and focused gates.

Its `rehearse` phase copies current working bytes into an exact verified `%TEMP%` target and produces a receipt binding the manifest digest, baseline and file SHA-256 values, tool versions, actual changed-path digest, finding delta, and gate results. `apply` accepts only a matching receipt and rechecks every source precondition before replaying the identical operation. Hard graph edges are collision membership, defining module/symbol, static and type-only import, dynamic target, export/facade, shared consumer, and generated artifact. Directory ancestry, semantic similarity, and clone evidence are annotations only.

Before mass execution, focused detector-teeth tests must prove stale-input refusal, target collision rejection, unresolved dynamic-reference refusal, changed-path allowlist mismatch, concurrent edit refusal, generated-owner handling, zero-new-finding deltas, and exact live replay after rehearsal. Module and symbol renames require separate fixtures because module moves have filesystem, packaging, and import-path consequences that symbol-only transforms do not.
