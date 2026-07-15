---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S12'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Retarget registry callable strings while retaining authority taxonomy paths

## Scope

- `src/cadrumo/_data/registry TOML callable targets`

## Description

- Ground registry executable targets in the schema, loader, and representative fragments.
- Classify `consumer` and `parser` as executable product targets while preserving authority identifiers.
- Retarget only anchored `consumer` and `parser` values from `aeat.*` to `cadrumo.*`.
- Parse every registry TOML file and audit the exact diff and old-target residue.

## Outcome

Retargeted 621 executable values across 250 TOML fragments: application-link
`consumer` module/callable paths and extraction-profile `parser` callables now
start with `cadrumo.`. No `consumer` or `parser` value beginning with `aeat.`
remains.

The edit changed exactly 621 lines and only the proven field values. The
`src/cadrumo/_data/registry/aeat` directory remains the authority taxonomy.
Schema identifiers such as `id = "aeat.user_profile"`, source identifiers,
official URLs, legal citations, hashes, evidence, and ordinary AEAT prose were
not changed. The preserved registry contains 28,931 lines with lowercase
`aeat`, all outside the two executable target shapes addressed by this Step.

All 16,273 registry TOML files parsed successfully with the standard-library
TOML parser. The exact diff audit found zero unexpected changed lines,
`git diff --check` passed, and the dynamic-target residue check returned zero.

## Notes

The real full-tree registry loader could not start because the package's error
registry still contains former product module paths; importing
`cadrumo.core.errors.CoreError` therefore fails its registry binding. That is
the expected open S14 dependency and is not a TOML parse or schema error. No
Python file was modified, so Ruff was not applicable.
