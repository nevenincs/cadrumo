---
tags:
  - '#audit'
  - '#just-tooling-bootstrap'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-just-tooling-bootstrap-research]]'
  - '[[2026-06-04-just-tooling-bootstrap-adr]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# `uv-venv-lock-workaround` Audit

## VENV-001 | HIGH | `uv sync` is not dependable in this shared Windows worktree

The shared `.venv` contains long-lived locked executable and native-extension files.
The persistent lock on `.venv/Scripts/vaultspec-rag.exe` prevents exact `uv sync`
from replacing or pruning the environment. Additional native locks were observed on
`pydantic_core/_pydantic_core.cp313-win_amd64.pyd` and
`tree_sitter_language_pack/_native.pyd`.

The durable workaround is to avoid exact environment reconciliation for routine
bootstrap. `just install` and `just sync` now perform additive installs with
`uv pip install --editable ".[workbook-windows]" --group dev`, which repairs missing
dependencies and editable metadata without removing locked executables.

## VENV-002 | HIGH | Tooling environment is now internally compatible

The venv was repaired without `uv sync`:

- The local `aeat` project was reinstalled editable with no dependency pruning.
- `pydantic-core` dist-info metadata was restored from a clean wheel target while
  leaving the locked native extension in place.
- `tree-sitter-language-pack 1.6.1` was installed into `.venv/overlay-site`, and
  `.venv/Lib/site-packages/aeat_overlay_site.pth` inserts that overlay before base
  site-packages for new Python processes.
- The base tree-sitter dist-info was aligned to `1.6.1` so metadata checks match the
  runtime package selected from the overlay.

Verification:

- `uv run --no-sync python -c "import aeat"` resolves to `src/aeat/__init__.py`.
- `just tooling-doctor` passes.
- `uv pip check --python .venv/Scripts/python.exe` reports all installed packages
  compatible.
- `uv lock --check` passes.

## VENV-003 | MEDIUM | Semgrep remains a `uvx` executable despite being declared

`semgrep 1.85.0` is installed as a Python distribution in the venv, but this Python
3.13 environment still does not expose a `semgrep` console script. The dependable
security endpoint remains `uvx --from semgrep semgrep`, which is now verified by
`just tooling-doctor` and used by `just audit-security` when no workstation
`semgrep` executable exists.

## VENV-004 | INFO | Workstation tools are explicit

`just workstation-tools` now verifies or installs the workstation CLI prerequisites
for the audit surface: `uv`, `just`, `node`, and `npx`. On Windows, it uses Scoop.
The duplication scanner remains pinned at the recipe level through
`npx --yes jscpd@4.2.0`.
