---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-03'
modified: '2026-07-03'
body_hash: 'sha256:cdbe701b267d7275600e05ecfef8bf2da2611f0d7e3e91cf7dbd216e4852bfba'
step_id: 'S15'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
---

# Add a loud loader refusal that raises a load error naming the fragmented layout when an inline bindings or formulas table appears in revision.toml

## Scope

- `src/aeat/domain/calculations/registry/_loader.py`

## Description

- Add the loud loader refusal for an inline section table in revision.toml.

## Outcome

Done in `e99a3a9ad3`: `_merge_revision_manifest` raises RegistryLoadError naming the '<section>/' fragment subdirectory when a section field appears inline. Verified by injecting `[[revisions.X.bindings]]` into a migrated revision.toml — the loader refuses with the layout-naming error.

## Notes

Verified live at HEAD (injection test).

## Honesty-review correction (2026-07-03)

The Outcome above cites the wrong commit. The loud loader refusal landed in `2cf772da94`, not `e99a3a9ad3`. Durable non-tautological regression tests for the refusal were added later in `f431e6a819` (`test_loader_directory_mode.py`). Correction recorded by the D6 campaign-close honesty review; see the 2026-07-03 arch-remediation-registry-format audit.
