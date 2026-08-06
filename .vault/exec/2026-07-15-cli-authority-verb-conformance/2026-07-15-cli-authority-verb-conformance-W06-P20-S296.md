---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:911d273e81c369e293596f3d289832ffc6d92e94594239854040db0c1707a513'
step_id: 'S296'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Guard the load-bearing wizard schema re-exports against a tidy-up deletion, since the re-export idiom looks redundant and removing it silently drops both profile verbs from the MCP surface

## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`

## Description

- Ground the Step against the live surface: the bridge has moved out of the named file to the sibling `_wizard_payloads` re-export module, which imports `ConfigProfileCreateResult`/`ConfigProfileEditResult` from `application.wizard` in the `X as X` idiom; it is a `*payload*`-named module the discovery walk imports.
- Measure the real dependency in four fresh interpreters (bridge importable/blocked via a meta-path finder, never a file deletion) for both surfaces, building each the production way. Result: the CLI contract/manifest surface (`aeat app contract` via `command_schema_refs`) carries both profile schemas with the bridge and drops both without it; the MCP surface carries both either way, because the landed identity fix imports `application.wizard` at module level in the server and harness, self-seeding the two schemas. The Step's premise that deletion drops the verbs from the MCP surface is stale; the guard is scoped to the surface that actually depends on the bridge.
- Correct the stale self-contradicting comment in `_config_payloads.py` that still claimed "the re-export at the top is what makes registry discovery reach them" — there is no such re-export in that file; point the reader at `_wizard_payloads` and the header note.
- Add a fresh-subprocess guard to `test_json_schema_conformance.py`: in a clean interpreter that never imports the wizard package, build the CLI manifest and assert both profile schema keys are present, failing with a message naming the keys and the importer to restore. Pair it with an anti-tautology test that blocks the bridge and asserts both keys disappear.
- Enroll the conformance test file in the existing `S603` per-file-ignore list (alongside `test_lazy_command_tree.py` and the other subprocess-driving CLI tests) since the guard shells `sys.executable -c <fixed script>`, the controlled-argv pattern the ruff heuristic cannot see.

## Outcome

Verified at HEAD `19ab62dc0ef77c6aaa16b3d0c0388dbce3bb9061`.

Four-case measurement (fresh interpreter each): CLI contract bridge-on create=True edit=True; CLI contract bridge-off create=False edit=False; MCP bridge-on create=True edit=True; MCP bridge-off create=True edit=True. So only the CLI contract/manifest surface depends on the bridge.

Command: `uv run --no-sync pytest -p no:randomly -m "unit or integration" -n0 -q --no-header src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py::test_wizard_profile_schemas_reach_the_manifest_only_via_the_bridge_module src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py::test_deleting_the_bridge_module_drops_both_profile_schemas` — `2 passed in 10.53s`. Full file: same invocation over the module — `161 passed in 15.90s`.

No self-seed established by measurement: the guard captures `"cadrumo.application.wizard" in sys.modules` immediately after importing the payload-walk entrypoint and before running the walk; it is `False`, so the guard imports no wizard of its own and the only wizard import comes from the bridge during the walk. The anti-tautology test confirms the bridge is the sole registrar: blocking it drops both keys, which is impossible if the guard self-seeded.

Mutation-check per added assertion (real passes, defect fails):

- guard `assert not missing` (keys present via bridge): real=pass (missing `[]`); bridge-blocked defect → missing `["config.profile.create", "config.profile.edit"]` → fail.
- guard `assert not wizard_before_walk` (no self-seed): real=pass (`False`); a defect that imported wizard directly would set it True → fail.
- anti-tautology `create/edit not in present` when blocked: real=pass; if the guard self-seeded, the keys would survive the block → fail.

`ruff check` and `ruff format --check` clean on both touched source files.

## Notes

The Step's named file `_config_payloads.py` was stale — the bridge had moved to `_wizard_payloads.py`. Worked the live surface, not the named path, and recorded the measurement against the Step's wording. The MCP-premise correction is recorded plainly: the guard is scoped to the CLI contract/manifest surface, the only one the measurement shows depends on the bridge. A pre-existing cold-start `pointer_path` circular import (unrelated, uniform across all four cases) is sidestepped in the probe by warming the lazy core exports before config resolution.
