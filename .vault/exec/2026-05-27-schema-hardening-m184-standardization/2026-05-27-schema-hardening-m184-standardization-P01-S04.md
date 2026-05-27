---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
step_id: 'S04'
related:
  - '[[2026-05-27-schema-hardening-m184-standardization-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `schema-hardening-m184-standardization` `P01.S04`

Records the Modelo 184 standardization review outcome, the post-split
reviewability baseline, and the next single-file modelo to take onto
the directory-fragment substrate.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m184-standardization-plan.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m184-standardization/2026-05-27-schema-hardening-m184-standardization-P01-S04.md`

## Description

The S01 inventory mapped the M184 single-file source into a 13-fragment
directory layout matching the established loader contract. The S02
mechanical split landed `manifest.toml` plus the
`revisions/2015-y-siguientes/` fragment tree without altering any
casilla definition, binding selector, deadline window, or
detail-record row builder. The S03 verification confirmed loader
equivalence (single-file vs directory-mode read parity), referential
integrity, committed registry validation, and end-to-end
detail-record row-set assembly + round-trip behavior continue to
hold from the fragment layout.

The post-split reviewability baseline is locked at: 13 TOML
fragments, largest fragment 95 lines (deadline windows), no single
fragment over 100 lines. The original 184.toml is removed; the
fragment tree is the canonical source. The reviewability ceiling
the directory layout now offers also covers the `casillas/`,
`constructs/`, and `bindings/` per-fragment slots without disturbing
the loader merge order or the deterministic snapshot fingerprint.

The remaining single-file modelos under the root registry tree are
`193.toml` (478 lines), `347.toml` (373), `309.toml` (363),
`360.toml` (324), `036.toml` (300), `308.toml`, and `840.toml`.
`193.toml` is the largest and therefore the next single-file
normalization edge; the same mechanical split strategy (inventory ->
manifest + revisions split -> directory-loader verification ->
baseline record) carries over with no contract change required.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_184_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- Result: covered by the S03 verification pass (32 passed) — no
  additional tests required at the standardization-record step.
