---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
body_hash: 'sha256:37bce5a2053edc6c61b3f10132805f66a26ab766e38259202c7672d91555af05'
step_id: 'S41'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Build and inspect the root wheel for only cadrumo import members

## Scope

- `local root wheel artifact`
- `pyproject.toml`
- `packaging/cadrumo_data_official/hatch_build.py`
- `dev/packaging/smoke_split_install.py`
- `dev/packaging/tests/test_cadrumo_data_distribution.py`

## Description

- Reconcile the root console-script metadata with the user-approved Cadrumo rename authority while preserving every other metadata byte.
- Build a fresh root wheel into an external temporary acceptance directory.
- Inspect wheel metadata, entry points, RECORD coverage, archive members, companion-payload exclusions, and compressed size.
- Install the wheel with real dependencies into a fresh virtual environment and prove canonical import, version, executable, and former-import refusal behavior.

## Outcome

The fresh root artifact is `cadrumo-0.1.1-py3-none-any.whl`, reports `Name:
cadrumo` and `Version: 0.1.1`, and is 41,881,051 bytes (41.881 decimal MB),
below PyPI's 100 MB per-file cap. Its 19,183 RECORD-covered archive members
comprise 19,178 `cadrumo/` members and five distribution-metadata members, with
zero `aeat/`, foreign import-root, `cadrumo_data/`, or companion corpus-source
binary members. Entry points are exactly `cadrumo` and `cadrumo-mcp`.

The fresh isolated environment installed 67 real packages. `import cadrumo`
reported version 0.1.1, `import aeat` was unavailable, and the installed
`cadrumo --version` command printed `cadrumo 0.1.1`.

## Notes

- Concurrent work changed the human script to `aeat` and introduced an untracked CLI ADR purporting to supersede the accepted rename decision. That ADR was never presented to or approved by the user, so it is not authoritative under the required ADR workflow. Only the one script key was restored; the peer ADR was not edited, staged, or committed.
- Formal review found that the first wheel still carried one official `.docx` and one official `.zip` source binary because the split-owned suffix authority covered only PDF/XLS/XLSX. The root exclusions, official hook, split smoke gate, and exact companion membership test now classify both extensions; the corrected root contains neither file, and an official companion artifact contains both at their mirrored `cadrumo_data` paths.
- Final root evidence came from a stable `HEAD` archive overlaid with the separately captured reviewed `pyproject.toml`, preventing concurrent shared-tree metadata writes from changing the artifact during its build.
- The focused exact companion ownership test passed (`1 passed`), along with Ruff, formatting, lock, residue, diff, and plan checks.
- The wheel and virtual environment live outside the project and are acceptance artifacts only; neither is committed.
- No lock regeneration was performed. The official companion was built only to prove ownership of the two review-found paths; exhaustive two-companion acceptance remains S42.
