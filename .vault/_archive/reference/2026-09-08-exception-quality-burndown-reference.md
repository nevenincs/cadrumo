---
tags:
  - '#reference'
  - '#exception-quality-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:cd130ae52b798ce24a9647ea6550f8ba0885445c4333d41f7b45e83f2d003b58'
related:
  - '[[2026-09-08-exception-quality-burndown-research]]'
  - '[[2026-09-04-reachability-burndown-adr]]'
---
# `exception-quality-burndown` reference: `Exception quality burndown implementation`

## Summary

The campaign's defining pattern is trace, classify, change, and prove one bounded behavior at a time. The initial source inventory is discovery-only. Before editing a lead, read its defining module, each raise and catch, the registry definition if it is a Cadrumo error, and the real public boundary that can render or contain it.

For a newly registered or re-rooted leaf, test its concrete inheritance, live qualified registry binding, safe context, and required builtin compatibility. `src/cadrumo/adapters/persistence/storage/tests/test_errors.py:24` and `src/cadrumo/adapters/persistence/storage/bucket/tests/test_bucket_errors.py:51` are the local models. A class move needs its matching declaration in the correct `src/cadrumo/core/errors/registry/` shard because binding is qualified-name based at `src/cadrumo/core/errors/error_codes.py:246-294`.

For a translated raw failure, trigger the production malformed state and assert the typed result, cause preservation where promised, and absence of raw sensitive detail. For a CLI-visible error, use the real command spine and assert the runtime category/code, text or JSON rendering, and no traceback; `src/cadrumo/entrypoints/cli/tests/test_error_boundary_integration.py:77`, `src/cadrumo/entrypoints/cli/tests/test_json_error_contract.py:203`, and `src/cadrumo/entrypoints/cli/tests/test_ledger_exception_propagation.py:55-143` are the closest patterns. Existing source-wide hierarchy/registry checks remain relevant after a changed error family but are not the campaign's closure proof.

The first two site cards are deliberately small and behaviorally dissimilar:

| Site | Current behavior | Intended remediation | Focused evidence |
| --- | --- | --- | --- |
| `src/cadrumo/application/aeat_sync/workspace.py:51,619-957` | `AeatSyncWorkspaceProjectionError` can pass through `workspace_reader` and workbench generation without source-level containment. | Catch at the AEAT Sync reader and return the existing unavailable-source result; preserve an unavailable search state instead of falsely treating it as empty or crashing the workbench. | Extend `src/cadrumo/application/tests/test_workbench_generation.py` with malformed/mismatched AEAT Sync input and assert unavailable source, unavailable search, and a rendered Home. |
| `src/cadrumo/entrypoints/tui/navigation.py:297-343` | Local navigation/factory failures can escape `TuiApp.navigate_to` screen creation. | Contain at the app navigation boundary and render the existing fail-closed localized state without admitting a stale target or raising a Textual event failure. | Extend `src/cadrumo/entrypoints/tui/tests/test_app.py` with stale/locked and factory-failure routes; assert no replacement/crash and the refusal state. |

Use Terra-high to investigate the first site of each semantic shape: Pydantic-compatible validation, adapter translation, persisted-data integrity, CLI projection, action-bearing refusal, and third-party wrapping. Luna-max is appropriate only after a Terra investigation has fixed the target error family, category/key, real adverse input, and test pattern for a set of disjoint, semantically identical sites. Stop that delegation as soon as a site changes catch behavior, public boundary behavior, action policy, persistence semantics, or registry ownership.
