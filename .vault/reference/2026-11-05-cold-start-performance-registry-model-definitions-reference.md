---
tags:
  - '#reference'
  - '#cold-start-performance'
date: '2026-11-05'
modified: '2026-11-05'
body_schema: 'body-v2'
body_hash: 'sha256:5399b59509b3727c7eab9a6ab74d03fd39a8959fbe71136a817b7767034ec4d4'
related: []
---

# `cold-start-performance` reference: `Registry closure schema-build cost at import and first snapshot`

Measurements of where the registry import closure (`registry.authority`, `formula_runtime`, `schema`) and the first `130 1T 2026 CALCULATION` snapshot spend definition-time and first-validate cost, taken on CPython 3.13 and pydantic 2.14.2 on a shared Windows host with `PYDANTIC_DISABLE_PLUGINS=__all__`, as every production entry point sets it.

## Summary

- Pydantic plugin discovery: the first schema build in a process scans every installed distribution's entry points (`pydantic/plugin/_loader.py:22`), about 40 ms. Production hosts disable it (`src/cadrumo_runtime/host/bootstrap.py:21`, `src/cadrumo_runtime/host/frontend/cli/bootstrap.py:16`, `src/cadrumo_mcp/mcp/main.py:33`); a profile taken without that variable attributes the scan to whichever module builds the first schema, which was `src/cadrumo/core/casilla_id.py`.
- Module-level `TypeAdapter`s: twelve adapters were built at import, about 38 to 43 ms. The resolved governed-fact union (`src/cadrumo/domain/calculations/registry/facts/resolution.py`) and the repeated-row projection union (`src/cadrumo/core/filing_projection_ref.py`) were the costly ones. Built on first use they cost about 12 ms at import across the remaining adapters.
- Eager model completion: 20 models completed at import, about 27 ms. Seven use `STRICT_FROZEN_HIDDEN_INPUT_CONFIG` (`src/cadrumo/core/models.py`), which lacked `defer_build`; four use the accumulator configuration in `src/cadrumo/domain/calculations/registry/invoice_row_materialization.py`; the rest complete because a module instantiates them at import. With both configurations deferring, 9 models complete, about 5 ms.
- Class definition: 373 pydantic models cost about 165 ms to define, of which about 68 ms is `get_model_type_hints` evaluating stringified annotations (2,298 `ForwardRef` constructions, each a `compile`). 156 dataclasses cost about 84 ms, dominated by compiling their generated methods.
- First-snapshot schema builds: about 250 ms, of which `ModeloRevision` is 70 to 125 ms for 160 nested models. Each top-level model compiles its own validator; building `ModeloDefinition` before `ModeloRevision` raised the combined cost, so build order offers no saving.
- `BindingProvider` (`src/cadrumo/domain/calculations/registry/binding_provider.py`) is a discriminated union over every selector family, and `ModeloRevision` validation needs every member, so its imports cannot be demand-loaded on the snapshot path.
- Interleaved fresh-process medians over 20 rounds (base, lazy adapters, plus deferred configurations): closure import 1032, 978, 922 ms; first snapshot in-process 1456, 1459, 1431 ms. Host contention was severe (bare interpreter median 241 ms against a 77 ms minimum), so the deterministic build counts above are the firmer evidence.
- Authorities published from each source tree have identical component payload digests (4,435) and snapshot-proof cells (2,904) to the baseline publication.
