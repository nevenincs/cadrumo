---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:51b01231e4ea2b0c2e25c78b4d0d753bf72b922d8ff657dd45e9c0202c0a2013'
step_id: 'S166'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Hard-move the generated field-manifest authority and its native atomic capture/current-coordinate pair, owner generation, and neutral opaque comparison domain from _workspace_manifest.py into the sole public application/modelo/workspace_manifest.py defining module, correct its contributor owner to application.modelo.workspace_manifest, atomically migrate every production, S126-registration, test, dynamic, and tooling consumer to direct imports and delete the private module plus every package binding, and prove identity, generation, currentness, and sole-walker parity without a permanent allowlist, shim, alias, fallback, bridge, or re-export

## Scope

- `src/cadrumo/application/modelo/workspace_manifest.py`
- `retired src/cadrumo/application/modelo/_workspace_manifest.py`
- `src/cadrumo/application/modelo/__init__.py inert-namespace gate`
- `every affected production/S126-registration/test/dynamic/tooling consumer`
- `and focused manifest identity/generation/currentness/direct-import tests`

## Changes

- `M` `src/cadrumo/application/modelo/workspace_manifest.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_manifest.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_manifest.py -m integration -q` -> `pass` (15 passed)

## Notes

The bare file rename `_workspace_manifest.py` -> `workspace_manifest.py` had
already landed on HEAD as an unintended bystander inside an unrelated
operator commit (`bf72f024052c1715efa048ae0ac5474f5effa696`,
"vault(audit): record the modelo 200 2024/2025 split coherence escalation") --
a broad commit sweeping up a stray uncommitted rename from the shared
worktree. That commit carried only the mechanical `mv`: no capture pair, no
corrected contributor owner, no proof tests, and no `relocation:` subject tag.
This Step's diff is the remainder of the actual S166 deliverable that did not
ride along: the native atomic capture/current-coordinate pair
(`ModeloWorkspaceManifestCapture`, `ModeloWorkspaceManifestCurrentCoordinate`,
`capture_modelo_workspace_manifest`, `read_modelo_workspace_manifest_current_coordinate`),
the contributor-owner correction (`domain.calculations.registry` ->
`application.modelo.workspace_manifest`, matching the module that now actually
generates the manifest), and 7 new tests including the anti-remnant proof that
`cadrumo.application.modelo._workspace_manifest` no longer imports. No second
capture path, no re-export, no package-namespace binding. A pre-existing
`ty check` `unsound-assignment` finding at the untouched `_walk_annotation`
walker (present identically in the HEAD blob before this Step) is unrelated
type debt from the original module and out of this Step's scope.
