---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:fb9225631edccdf1faf0b82bb71de11685c28a8acf46ed28af1881860a42f9d0'
step_id: 'S20'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace secure-storage-performance-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S20 and 2026-08-22-secure-storage-performance-hardening-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Separate read-only settings and path calculation from directory, permission, logging, journal, and topology materialization and ## Scope

- `src/cadrumo/core/config.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Separate read-only settings and path calculation from directory, permission, logging, journal, and topology materialization

## Scope

- `src/cadrumo/core/config.py`

## Description

- Move storage topology creation, occupancy refusal, and root permission hardening from
  read-only config into canonical storage materialization ownership.
- Expose the mutator and mode lazily through the sole core facade and repoint all
  cross-package production and test consumers.
- Prove settings and derived-path reads create no storage state while materialization
  retains the prior security behavior.

## Outcome

`core.config` now owns settings and path calculation only. Filesystem mutation is explicit
and demand-loaded through the core facade. Focused storage/config tests pass and Ruff is
clean; independent review approved the final boundary.

## Notes

No compatibility shim or harness/client change was introduced.
