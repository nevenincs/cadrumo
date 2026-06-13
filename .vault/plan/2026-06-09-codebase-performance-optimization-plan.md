---
tags:
  - '#plan'
  - '#codebase-performance-optimization'
date: '2026-06-09'
modified: '2026-06-09'
tier: L3
related:
  - '[[2026-06-09-codebase-performance-optimization-research]]'
  - '[[2026-06-09-codebase-performance-optimization-adr]]'
---


# `codebase-performance-optimization` `Codebase Performance Optimization and Nested Parsing Audit` plan

## Wave `W01` - Registry optimization and parsed TOML snapshots

Implement compiled registry caching, formula AST caching, and Pydantic validation improvements to reduce baseline engine loading and execution overhead.

### Phase `W01.P01` - Compiled registry validated cache

Introduce persistent validation cache file for ValidatedRegistryAuthority loading to bypass expensive validation step on warm runs.

- [x] `W01.P01.S01` - Include user_profile/schema.toml in registry tree fingerprints; `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `W01.P01.S02` - Implement validation cache file checking and writing in _load_authority; `src/aeat/domain/calculations/registry/_authority.py`.
- [x] `W01.P01.S03` - Add tests verifying registry validated cache loading speed and modification invalidation; `src/aeat/domain/calculations/registry/tests/test_authority.py`.

### Phase `W01.P02` - Formula AST caching

Add LRU caching to AST-traversing reference resolution and topological sorting functions in the formula runtime graph.

- [x] `W01.P02.S04` - Add lru_cache to _casilla_reference_resolver, input_casilla_alias_map, and formula_evaluation_order; `src/aeat/domain/calculations/registry/_runtime_graph.py`.
- [x] `W01.P02.S05` - Add lru_cache to expression ref collectors for FormulaExpression; `src/aeat/domain/calculations/registry/_runtime_graph.py`.

### Phase `W01.P03` - Pydantic model-config/deserialization optimization

Optimize Pydantic model configuration and validate_python usage across hot boundaries to reduce overhead.

- [x] `W01.P03.S06` - Reuse TypeAdapter(AnyHttpUrl) instance in _extract.py instead of creating it inline; `src/aeat/adapters/inbound/justificante/_extract.py`.

## Description


## Steps







## Parallelization


## Verification
