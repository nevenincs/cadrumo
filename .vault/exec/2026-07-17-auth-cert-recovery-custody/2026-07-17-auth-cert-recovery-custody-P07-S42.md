---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S42'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Add an AST recurrence gate, patterned on test_wizard_prompter_singularity.py, that bans module-global _override_* factory state and public override_* setters in production, exempting only the sanctioned core.config.override_settings

## Scope

- `src/cadrumo/adapters/persistence/storage/blob_store/tests/test_materialisation.py`

## Description

- Add `src/cadrumo/tests/test_override_seam_singularity.py`, patterned on `test_wizard_prompter_singularity.py`, using the shared `_inventory` production-tree helpers and the `source_tree_ast` fixture.
- Implement two pure `(display_path, tree) -> list[str]` AST detectors with no stored baseline and no allowlist: `override_global_state_violations` (bars any assignment binding an `_override_*` name, plus `global _override_*` rebinds) and `override_setter_function_violations` (bars any public `override_*` function definition).
- Pin the single sanctioned carve-out by name and module: `override_settings` in `core/config.py` (a scoped `contextvars`-backed context manager backed by a ContextVar named `_settings_override`, not an `_override_*` slot), so a second `override_*` cannot hide behind it.
- Add anti-vacuity tests pinning the production scan surface is non-empty and the carve-out anchor exists as exactly one definition in the carve-out module.
- Add discrimination tests feeding each detector the seam shape it must flag and the sanctioned shape it must not.
- Prove the gate against the real tree scan by planting a synthetic production violator, confirming both tree-scan rules go red naming file and line, then removing it and confirming green.
- Place `pytestmark = [pytest.mark.unit, pytest.mark.hex_core]` as the first test statement, before the `TYPE_CHECKING` block, satisfying the marker-integrity gate.

## Outcome

- The gate is green with an empty allowlist: `test_override_seam_singularity.py` passes all ten cases; the production tree carries zero `_override_*` globals and one sanctioned `override_settings`.
- Discrimination proof: with the planted violator the two tree-scan rules failed, each naming the synthetic module's file and line plus the rule text; after removal both passed again.
- `test_marker_integrity.py::test_module_pytestmark_is_first_test_statement` passes for the new file; ruff is clean; `--collect-only` collects the ten cases without error.
- The process-wide override test-hook class that let the deleted `override_wizard_prompter` and `override_secret_store` hide is now structurally barred from returning to production.

## Notes

- The originating Step row named `test_materialisation.py` as the scope file; the gate ships under the convention-matching name `test_override_seam_singularity.py` (mirroring `test_wizard_prompter_singularity.py`) rather than in the materialisation test module, which is the correct home for a tree-wide structural gate.
- The seam deletion (Step S41) was committed at `009ed60`; this gate is a separate atomic commit at `7305fd3ae2`.
- No incidents, no skipped work, no scaffolds left in code — the synthetic violator was a temporary untracked file, removed after the discrimination proof and never staged.
