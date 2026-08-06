---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:18cf6414a30fd9637ab7d71e22f456d57b8fb3e865afd4a2f0992527954064ae'
step_id: 'S09'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Scaffold the aeat-data distribution build with its own pyproject reading the same source tree, force-including the corpus binaries under an aeat_data package with mirrored relative paths

## Scope

- `packaging/aeat_data/pyproject.toml`

## Description

- Scaffold the `packaging/aeat_data` hatchling project declaring the `aeat-data` distribution.
- Add a `hatch_build.py` build hook that force-includes only the corpus binaries from the one shared source tree, remapped to `aeat_data/_data/corpus/...` — the exact layout the `S13` corpus locator seam resolves.
- Pin the distribution's version to a synced literal locked to the root package version (parity-gated by `S11`).
- Add the Apache-2.0 license declaration and a README.
- Commit `354ff2e8dd`.

## Outcome

- Companion wheel measures approximately 139 MB and packages exactly 190 corpus binaries.
- Full sdist and wheel roundtrip builds succeed.

## Notes

No incidents. No skipped work.
