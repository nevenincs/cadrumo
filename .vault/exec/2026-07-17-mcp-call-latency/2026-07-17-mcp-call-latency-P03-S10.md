---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-19'
step_id: 'S10'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

# Prove with a real-behavior test that mutating the compiled cache on disk makes strict load refuse and rebuild from TOML, so the cache is never a second authority

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_compiled_registry_cache.py`

## Description

- Add `test_mutating_the_cache_through_the_loader_rebuilds_byte_equivalently_from_toml` to `test_compiled_registry_cache.py`: a real-behavior loader-integration proof that a mutated on-disk cache can never become a second authority.
- Cold-compile the real bundled tree through `load_registry_tree` into an isolated cache directory to capture an independent TOML oracle, then flip a payload byte on the written cache file so its embedded integrity digest no longer matches.
- Clear only the in-process memo and reload: assert the mutated cache is refused, the loader rebuilds from TOML byte-equivalently to the oracle (both the modelo set and the catalogues), and a fresh valid cache replaces the poisoned one so the mutation does not persist.

## Outcome

Full `test_compiled_registry_cache.py` passes (4 passed): the S08 module-contract trio plus the S10 loader-integration proof. Gates green on the authored test: `ruff check`, `ruff format --check`, `ty check`. The proof exercises real behavior throughout - the real bundled registry, the real compile path, a real filesystem cache directory, and the real `load_registry_tree` entry point - with no mocks, stubs, skips, or tautological assertions; expected values are the loader's own cold-compile oracle, never hand-computed.

## Notes

Scope note on the guarantee: "mutating the cache" is a byte corruption, which the integrity digest catches (digest mismatch -> refuse -> rebuild). A full replacement with a self-consistent forged frame (valid structure and matching digest) is out of the cache's threat model per the ADR - install byte integrity is owned by the package-manager digest chain, and the cache directory is user-owned - so the test asserts the corruption-refusal contract the plan names, not resistance to a local forger who can also rewrite the digest.
