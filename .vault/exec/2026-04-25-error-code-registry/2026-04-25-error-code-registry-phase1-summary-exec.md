---
tags:
  - "#exec"
  - "#error-code-registry"
date: 2026-04-25
modified: '2026-04-25'
title: "error-code-registry phase1 summary"
related:
  - "[[2026-04-25-error-code-registry-plan]]"
  - "[[2026-04-25-error-code-registry-adr]]"
  - "[[2026-04-25-error-code-registry-research]]"
---

# error-code-registry phase1 summary

## Scope

- Converted `aeat.core.errors` from a single module into a package while preserving
  the public `from aeat.core.errors import ...` surface.
- Added `aeat.core.errors._registry` with the strict `ErrorCategory`, `ErrorCode`,
  and `ErrorEnvelope` models plus the registration, rendering, exit-code, and
  secret-scrubbing helpers.
- Bound registered codes to imported `AeatError` subclasses at declaration time
  through `AeatError.__init_subclass__`.
- Added the shared CLI boundary in `aeat.entrypoints.cli._errors` and applied it from the
  root Typer app while explicitly skipping `workflow run` and `workflow next`
  per the #393 coordination boundary.
- Replaced the remaining direct MCP launch holdout with a named `AeatError`
  subtype so the registry covers that path as well.

## Design notes

- The category enum owns the stable stderr prefix vocabulary and placeholder
  exit-code policy, keeping category policy separate from per-error metadata.
- The registry implementation is strict-but-phaseable: a concrete subclass gets
  a bound registry row automatically, and static tests enforce that the
  imported tree stays covered.
- The CLI boundary emits to stderr only, scaffolds `--json` detection for the
  follow-on issue, and preserves a test-only re-raise path via
  `error_boundary_under_test()`.
- The stderr writer forces UTF-8 when possible and falls back cleanly when the
  active stream encoding cannot represent the localized text.

## Coordination note

Per the issue instructions, the decorator pass deliberately leaves
`aeat workflow run` and `aeat workflow next` untouched on this branch. That
follow-up remains deferred until sibling issue #393 merges.
