---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:b0c268c56204f49f823b204a99755f35234239ffa9e9715853421049c45a91cb'
step_id: 'S48'
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
     The S48 and 2026-08-22-secure-storage-performance-hardening-plan placeholders are machine-filled by
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
     The Attach execution policy to every config subtree callback and group and ## Scope

- `src/cadrumo/entrypoints/cli/_config/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Attach execution policy to every config subtree callback and group

## Scope

- `src/cadrumo/entrypoints/cli/_config/`

## Description

- Attached immutable execution policy directly to every live config leaf callback.
- Enrolled callbackless config groups through inert, state-free metadata callbacks while preserving Typer help and missing-command behavior.
- Declared specialised registry, calculation, browser, network, Google, filing, custody, and encrypted-fact authorities where handlers enter them.
- Added a live exact-set census gate, an externally injected unclassified specimen, representative authority assertions, and group semantic-parity coverage.
- Revised the plan canonically after execution proved that deleting config risk rows before the S52 consumer migration breaks existing HITL safety consumers.

## Outcome

The materialised CLI census contained 106 config nodes and no missing execution
policy. Focused Ruff and type checks passed. The selected unit lane completed
with seven passing tests; config help and leaf dispatch remained unchanged, and
bare non-executing groups retained their usage output and exit status.

## Notes

An attempted early removal of config risk rows made the existing destructive
versus archive safety tests fail because operator-surface and MCP consumers have
not migrated yet. The rows were restored without content change. S48 was
narrowed through the canonical plan CLI to attachment and enrollment; S52 now
explicitly owns removal of every legacy row after its consumers migrate. This is
an ordering correction, not a claim that the legacy authority has been retired.
