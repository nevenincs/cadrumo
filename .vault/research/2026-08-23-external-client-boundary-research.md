---
tags:
  - '#research'
  - '#external-client-boundary'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:8bc00fb90eb37da0a3b5695c81a79b61147d4414e6e5ea87187813bd4e634a1e'
related: []
---
# `external-client-boundary` research: base product and external client dependency boundary

The live `aeat` grammar already rejects `app agent`, but executable documentation and several base-package modules still encode knowledge of the separate `cadrumo-harness` consumer. The evidence favors a hard dependency inversion: the base product owns protocol-neutral commands, schemas, and application services; external clients derive their adapter policy without commands, configuration, storage categories, artifacts, or release steps in the base product that identify them.

## Findings

### The command implementation is gone but its executable documentation survived

Commit `c923d86938f` deleted the production agent-workspace command, payloads, registration, and narrow tests. Current `aeat app --help` has no `agent` child, while `docs/_sequences/contracts/workstation-setup/install-agent-harness.seq:2` still invoked `aeat --format json app agent`. The documented-command conformance failure is therefore a stale executable contract, not a missing command implementation.

### The base application still contains external-adapter policy

`src/cadrumo/application/operator_surface/_manifest.py:181` models required MCP exposure and `src/cadrumo/application/operator_surface/_manifest.py:603` enforces client-specific exposure policy. Consumers live under `src/cadrumo-harness/src/cadrumo_harness/mcp/`, including `_tools.py`, `_toolsets.py`, `_persona_scope.py`, and `_meta_tools.py`. Keeping the projection in the base package reverses the dependency even though the runtime import direction points from harness to base.

### Consumer identity leaks beyond the projection

Base corpus-search documentation names harness mapper and resource functions at `src/cadrumo/application/corpus_search/_models.py:12` and `_citation_lookup.py:22`. Base configuration and storage taxonomy describe MCP session telemetry at `src/cadrumo/core/config.py:498` and `src/cadrumo/core/_storage_taxonomy_locations.py:167`. These names make base semantics depend on one consumer rather than a generic capability.

### The product release cohort also treats the client as a base artifact

`dev/packaging/python_cohort.py:100` and `dev/packaging/release_cohort.py:139` identify the harness inside the product cohort. `.github/workflows/publish-release.yml:605` publishes a client marketplace destination from the product release. This coupling can cause an external-client defect or credential gap to alter the base product release outcome.

### Existing decisions conflict and need explicit supersession

`2026-06-30-agent-harness-adr` and `2026-07-03-claude-ecosystem-packaging-adr` required a base-mounted materializer and later `aeat app agent`. `2026-07-02-agent-harness-refoundation-adr` instead describes the CLI as a black box, but retains later implementation coupling. The new direction is a pivot, not a clarification, so the client-aware clauses cannot remain accepted alongside it.

### Options

Keeping only the command deletion is insufficient because base policy and release code still identify the consumer. Renaming agent terms to neutral words without moving policy hides rather than repairs the dependency. Moving client adaptation, documentation, artifacts, and release ownership out of the base product preserves generic contracts and makes the dependency one-way.

## Sources

- `c923d86938f`
- `docs/_sequences/contracts/workstation-setup/install-agent-harness.seq:2`
- `src/cadrumo/application/operator_surface/_manifest.py:181`
- `src/cadrumo/application/operator_surface/_manifest.py:603`
- `src/cadrumo/application/corpus_search/_models.py:12`
- `src/cadrumo/application/corpus_search/_citation_lookup.py:22`
- `src/cadrumo/core/config.py:498`
- `src/cadrumo/core/_storage_taxonomy_locations.py:167`
- `dev/packaging/python_cohort.py:100`
- `dev/packaging/release_cohort.py:139`
- `.github/workflows/publish-release.yml:605`
- `2026-06-30-agent-harness-adr`
- `2026-07-02-agent-harness-refoundation-adr`
- `2026-07-03-claude-ecosystem-packaging-adr`
