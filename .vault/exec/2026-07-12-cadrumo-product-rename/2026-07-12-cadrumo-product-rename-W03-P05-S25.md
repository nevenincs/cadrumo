---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:48fc0e66b24fbb6b7941294e6a1cf6640c0bd61ad69310825c9d8b63599fed99'
step_id: 'S25'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Bind CLI program identity to `aeat` and its version and help product surfaces to CADRUMO

## Scope

- `src/cadrumo/entrypoints/cli and direct CLI structural tests`

## Description

- Derive the Typer root name, lazy root registration, pinned program name, and
  real-process argument recognition from `PRODUCT_IDENTITY.cli_executable`.
- Render the short version surface from `PRODUCT_IDENTITY.display_name` while
  retaining `Cadrumo` for sentence prose and the lowercase distribution
  identifier in package diagnostics.
- Retarget installed-console and fast-path structural tests to the sole `aeat`
  executable, the contextual Cadrumo/CADRUMO display contract, and preserved
  `AEAT` authority language.
- Verify the focused CLI surface with Ruff, real subprocess tests, and live
  `uv run --no-sync` command probes.

## Outcome

The runtime mechanics from commit `0589de6f0fab3e238998bd0d57f8be07c5903df4`
remain correct: the installed `aeat` entry point pins `aeat` in generated
command guidance, recognises its real-process argument stream, and reports
exactly `CADRUMO 0.2.1` on the short version surface. The CLI source uses
`Cadrumo` in sentence prose and `CADRUMO` for the rendered identity heading;
root help retains `AEAT` only for the Spanish tax authority.

The focused acceptance suite now includes a real installed-console subprocess
test that jointly proves the exact version line, the `CADRUMO` help heading,
`aeat` command guidance, preserved `AEAT` authority language, and absence of a
human `cadrumo` alias beside the active interpreter. Nineteen focused CLI
integration tests pass across fast-path help and version, cold startup,
installed-console discovery, former-state refusal, and curated help resolution.

## Notes

- Direct probes passed for `uv run --no-sync aeat --version`, default Spanish
  `aeat --help`, and English `aeat --language en --help`; a command lookup
  confirmed that no `cadrumo` human executable is installed.
- Ruff lint and format checks pass on the focused CLI source and tests. Ty
  passes on both focused test files. A broader diagnostic of unchanged
  `cli/__init__.py` still reports its pre-existing dynamically attached Typer
  sentinel attribute; S25 neither hides that diagnostic nor expands into an
  unrelated typing repair.
- No compatibility executable, Python import shim, state reader, or migration
  path was added.
