---
tags:
  - '#reference'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:6735af82b469f1f733425dc468068178a54b08cee7794a4bf040b89f5915a7f3'
related:
  - '[[2026-07-12-cadrumo-cli-executable-adr]]'
---

# `cadrumo-product-rename` reference: entrypoint and package-root audit

This audit records the completed Cadrumo product-name entrypoint repair across
the package, console-script, pytest, and MCP surfaces.

## Summary

`src/cadrumo/core/product_identity.py` is the implemented runtime identity
authority. It identifies the display name and Python package as Cadrumo,
preserves AEAT for the Spanish authority, and sets `cli_executable` to `aeat`.
The accepted executable ADR is the naming authority: Cadrumo is the product,
`aeat` is the sole human command, and `cadrumo-mcp` is the distinct MCP
executable.

`[project.scripts]` in `pyproject.toml` binds `aeat` directly to
`cadrumo.entrypoints.cli:main` and `cadrumo-mcp` to
`cadrumo.entrypoints.mcp:main`. The CLI deliberately renders `aeat` as its
program name. `import cadrumo` is supported, while `import aeat` remains
unsupported; there is no `aeat` Python shim and no `cadrumo` human-command
alias.

The root pytest hook and console-import test now target the Cadrumo package.
The cold-process regression proves that `import cadrumo` succeeds and
`import aeat` fails, preserving the one-package runtime boundary.

The root CLI integration tests locate the installed `aeat` executable beside
the active interpreter and run it with isolated Cadrumo configuration. They
prove the rendered help exposes Cadrumo product controls without depending on
an inherited local configuration.

## Configuration boundary

`_CadrumoDotEnvSettingsSource` excludes exactly the former product dotenv
names before strict settings parsing. It does not weaken validation: a real
dotenv regression retains `AEAT_AUTH_PROVIDER` as an authority setting and
proves an unrelated key still raises `ValidationError`. This remains a hard
Cadrumo configuration cut rather than a dual-reader compatibility path.

The CLI-reference generator imports `cadrumo.entrypoints.cli` directly and
uses an isolated configuration environment. It clears inherited product
settings and pins its output language before collecting live commands.

## Verification evidence

The completed repair was verified with a fresh `uv sync`, `aeat --help`, a
fresh-process `import cadrumo`, the deliberate failure of `import aeat`, and
the affected real-behavior pytest and documentation-conformance suites. The
MCP command is `cadrumo-mcp`, not `aeat-mcp`.
