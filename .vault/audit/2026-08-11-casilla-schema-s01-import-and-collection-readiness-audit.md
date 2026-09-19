---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:49b4c90cf2c4183ad105a38bfb7cb95a59dad61648fb2540148c5dd65289f92d'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `s01 import and collection readiness`

## Scope

Read-only closeout review of `W01.P01.S01` against the current shared tree, the `casilla-schema` research and four accepted ADRs, the campaign plan, and the seven collection-readiness repair surfaces. The review followed the files across the concurrent landing: the `NoRecoveryOutcome` import is present in ancestor commit `e7cbbc4c4e5`, the REAGP catalogue, legal authority, and declarant-identity test changes landed in `25154f65ce`, and four test repairs remain unstaged. Unrelated shared WIP was excluded.

The legal chain for `IvaCategory.REAGP_COMPENSATION` is correctly owned by the IVA catalogue and legal catalogue: the category cites `ley-37-1992:art-130`, the legal entry points at the bundled consolidated LIVA `#a130`, and its required text and quoted paragraph match article 130.Dos. The ledger-aggregation repair uses real production types and explicit deduction provenance, introduces no fake, mock, stub, patch, monkeypatch, duplicated calculation, or compatibility bridge. Removing the exact catalogue length assertion improves the gate by testing coverage as a property.

Current verification establishes the collection objective itself: `cadrumo.application.modelo` imports successfully; the focused collection-readiness lane passes 53 tests; `aeat app registry verify` reports 73 modelos, 94 revisions, and 799 legal references; full collection reaches 28,934 tests with zero collection errors; Ruff, format, BasedPyright, and diff-check are green. These results prove clean import and collection, but they do not override the test-truthfulness and closeout-record findings below.

## Findings

### export-refusal-coverage | medium | The repaired export test no longer exercises the export refusal

`test_export_declarant_identity_grounding.py` still claims in its module text and test names to prove the export declarant-identity refusal, but `_render` now calls only the generic `format_profile_path_requirements` helper. No export producer, refusal, or public export-facing function is invoked. The assertions therefore prove the formatter against labels produced by the same profile-preflight subsystem, while the operator-visible export behavior named by the test can regress without this file firing. This is a truthful-coverage loss, not a compatibility restoration.

### complexity-baseline-namespace | medium | The rename gate admits stale debt that its collector cannot measure

`test_complexity_baseline_keys_reference_current_owner_namespaces` now accepts keys beginning with `dev/registry/`, while the production complexity collector targets only `src/cadrumo`. The committed baseline currently contains seven such entries. A strict complexity probe reports them as resolved because the collector never visits that namespace, so the test blesses permanently unpoliced debt while claiming the keys belong to current measured owners.

### complexity-private-import | low | The rename gate crosses the owner boundary through a private constant

`test_dev_rename_audit_tools.py` imports `dev.audit.complexity._BASELINE_PATH` under a public-looking alias. The quality rule rejects cross-package private imports. The baseline location needs a public owner surface, or the test must verify the behavior without reaching through the underscore boundary.

### s01-execution-record | medium | The required S01 execution record is absent

The campaign plan states that every closed step has an execution record under the feature execution directory. That directory contains only `W01.P01.S02`; no `W01.P01.S01` record exists. The plan correctly still leaves S01 open. Green verification is necessary but is not, by the plan's own close protocol, sufficient to check the step off without the missing record.

## Recommendations

- Restore a real export-facing assertion for `export-refusal-coverage`, exercising the living public producer or refusal boundary rather than only the generic formatter. If the export refusal contract has genuinely been removed by the current-schema cut, rename and relocate the test so its claimed scope matches what it executes.
- For `complexity-baseline-namespace`, either extend the canonical complexity collector to measure the intended `dev/registry/` owner or remove the stale baseline rows and refuse keys outside the collector's measured roots. Do not preserve them through an allowlist-like namespace exception.
- For `complexity-private-import`, expose a public baseline-path owner API only if consumers genuinely need it; otherwise assert through `load_baseline` and the canonical command behavior without importing `_BASELINE_PATH`.
- After those repairs, rerun the focused lane and the clean full collect-only gate, author the required `W01.P01.S01` execution record with the exact current-tree evidence, and only then check S01 in the plan.

Verdict: **CHANGES REQUESTED.** The `NoRecoveryOutcome` import and the REAGP legal grounding are sound, no compatibility surface was restored, and the current tree demonstrably imports and collects 28,934 tests. S01 cannot honestly close yet because two medium test-truthfulness defects remain and its mandatory execution record is absent.

## Resolution review

### export-refusal-coverage | resolved | The false export claim and its dead constants were deleted

The misleading `test_export_declarant_identity_grounding.py` was deleted instead of being renamed into a claim it did not prove. The six profile-path and entity constants that existed only for the retired path were deleted from `_export.py`. Searches find neither the test nor any of those constants in the current tree. This resolution removes dead test capacity and production residue without restoring a private helper or compatibility facade.

### complexity-baseline-namespace | resolved | Every retained baseline key is live and measured

`test_complexity_baseline_keys_reference_current_owner_namespaces` now loads both baseline scopes through public `load_baseline`, requires a non-empty key set, requires every key to begin with `src/cadrumo/`, and requires every path portion to resolve to a current file. The regenerated baseline contains 531 unique keys. An independent production import probe confirmed all 531 satisfy the prefix and live-file predicates. No `dev/registry/`, `src/aeat`, or deleted-path baseline row remains.

### complexity-private-import | resolved | The test uses only the public owner API

The `_BASELINE_PATH` import and its alias are gone. The gate calls public `load_baseline` with its owner-defined default path, so the test verifies the canonical baseline without crossing a private package boundary.

### s01-execution-record | resolved | The step is checked with its matching execution record

The CLI-authored `W01.P01.S01` execution record now exists with `step_id = S01`, relates to the `casilla-schema` plan, records the canonical import, the removal of false collection repairs, and the clean repository-wide collection outcome. The plan marks `W01.P01.S01` checked and retains the exact original step text. The plan and execution record therefore satisfy the campaign's structural close protocol.

## Resolution verification

Independent current-tree verification produced these results:

- `cadrumo.application.modelo` imported successfully.
- A direct public-API baseline probe validated 531 unique keys, all under `src/cadrumo/` and all resolving to live files.
- The focused developer-audit file passed 5 tests in 7.83 seconds.
- Scoped Ruff reported all checks passed.
- Scoped BasedPyright reported zero errors, zero warnings, and zero notes.
- Scoped `git diff --check` passed.
- Full serial repository collection with project `addopts` cleared, `uv run --no-sync pytest --collect-only -q -n 0 --override-ini=addopts=`, exited zero with 28,927 tests collected in 69.87 seconds. A first independent run of the same gate also exited zero.

Resolution verdict: **PASS.** All four original findings are resolved. The deletion-first repair preserves the no-legacy rule, the complexity gate now measures only live canonical owners through a public API, the execution record and plan state agree, and the current repository imports and collects cleanly. `W01.P01.S01` can honestly remain closed.
