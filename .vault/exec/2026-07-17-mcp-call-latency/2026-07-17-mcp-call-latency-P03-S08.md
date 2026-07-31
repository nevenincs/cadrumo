---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:751235fe3eea01a6ed17fd63475d60ccf5790d21df7952f65492d6b0e78e7fb6'
step_id: 'S08'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

# Add a compiled ModeloDefinition-set cache keyed by the registry-tree fingerprint, strict-validated on deserialisation and deleted on any mismatch or deserialisation failure, exercised against the real bundled tree

## Scope

- `src/cadrumo/domain/calculations/registry/_compiled_cache.py`

## Description

- Add `_compiled_cache.py`: a strict-validated, fingerprint-keyed cache for the compiled `(modelos, catalogues)` set (ADR D3), so a warm process can skip the 17,276-file TOML parse.
- Key each cache file by the complete registry-tree fingerprint tuples plus the loader/compiler/schema source hash (reusing the loader's `_registry_disk_cache_key`), so a tree edit or compiler change yields a new key and a pre-change cache is never read.
- Frame the file as `version` + integrity `digest` + pickled payload; on read verify the schema version, the SHA-256 payload digest, and the exact structural shape `tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]`, deleting the file and returning `None` on any mismatch, deserialisation failure, or foreign shape.
- Write atomically via a sibling temp file and prune stale siblings past the retained-entry ceiling (reusing the loader's `_evict_stale_registry_pickles`).
- Add `test_compiled_registry_cache.py`: real-behavior contract tests against the real bundled tree and a test-owned cache directory - store/load strict-equality round-trip, a byte mutation refused and deleted, and a foreign-shaped digest-valid payload refused and deleted.

## Outcome

Module-contract tests pass (3 passed). Gates green on the two authored files: `ruff check` (All checks passed), `ruff format --check` (already formatted), `ty check` (All checks passed). The pre-existing cache and reviewability suites stay green (13 passed: `test_registry_reviewability.py`, `test_registry_disk_cache_loader_fingerprint.py`, `test_registry_cache_eviction.py`) - S08 is additive and does not yet touch `_loader.py`.

Serialisation choice: pickle, not pydantic JSON. The compiled models are strict and frozen (`RegistryModel`) and `FormulaExpression.args: tuple[FormulaExpression, ...]` combined with a `mode="before"` validator makes `model_validate_json` reject JSON arrays for the strict tuple (empirically confirmed round-trip failure), so pydantic JSON is not available without weakening the strict contract or editing the schema - out of scope for a derived cache. Pickle round-trips the exact frozen objects; the arbitrary-pickle surface is bounded by the user-owned settings cache directory (never a shared OS temp dir in production), by the payload being produced solely by this module's own compile, and by the embedded integrity digest plus structural type-check refusing any corrupt or foreign file. Because full pydantic re-validation of the deserialised models is unavailable (the same strict round-trip limit) and would in any case not catch a schema-valid mutation (an empty-modelos poison validates), the never-a-second-authority guarantee rests on the digest (catches every byte mutation) plus the structural type-check (catches a foreign shape).

Threat-model honesty: the embedded digest defeats accidental corruption, partial/interrupted writes, and a schema-valid poison written by a buggy or older writer (the exact case plain pydantic re-validation would wave through). It does NOT defend against a local process that already has cache-dir write access and can simply recompute the digest over a substituted payload - that residual attacker sits inside the same user-owned trust domain the ADR already accepts (the cache lives only in the user's settings cache directory, and install byte integrity is owned by the package-manager digest chain, not this cache). The digest is an integrity checksum, not a security signature.

## Notes

A compiled-registry disk-pickle cache already existed at HEAD (`_load_registry_tree_cached` in `_loader.py`, from the data-output-standardization campaign): measured cold compile 8.2 s versus warm pickle load 1.76 s on the bundled tree, so R5's warm-parse win is largely already realized. Its gap is exactly what D3 closes: it returns unpickled bytes verbatim with no integrity or strict-shape gate (a current-key poison pickle is served - the peer test asserts that as its control), so it can act as a second authority. S08 introduces the hardened home; S09 relocates the loader's inline pickle helpers into it, wires the loader to it, and updates the two peer cache tests in one atomic commit. The team lead was notified of this scope reframing before landing.

Docs stub: the new module needs a `docs/api/*.rst` stub (the `-n -W` build guards against module/stub drift). This should have ridden the S08 module-creation commit but was missed there; the team landed it as a dedicated follow-up (`python -m dev.docs.apidocs scaffold` output for `cadrumo.domain.calculations.registry._compiled_cache` plus the registry package toctree), alongside the regenerated stubs for the other new campaign modules. `scaffold --check` is clean at HEAD.

Between the S08 and S09 commits `_compiled_cache.py` reuses `_registry_disk_cache_key` and `_evict_stale_registry_pickles` from `_loader.py`; S09 relocates them so no duplication remains.
