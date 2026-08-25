---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:4816b21342e60d5ad959d8c8916f9cad378077647c17e725e9c78e8d3d78a7ab'
step_id: 'S246'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S246 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Repair the harness serial watchdog kill-switch and disarm lifecycle so the full integration suite terminates cleanly without weakening timeout enforcement and ## Scope

- `src/cadrumo-harness/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Repair the harness serial watchdog kill-switch and disarm lifecycle so the full integration suite terminates cleanly without weakening timeout enforcement

## Scope

- `src/cadrumo-harness/`

## Description

- Add a single generation-owned watchdog cancellation event and an idempotent disarm entry point.
- Disarm the active generation in the real server's unconditional shutdown path.
- Make Windows waits bounded and cancellation-aware while retaining immediate genuine-client death handling.
- Make POSIX polling cancellation-aware and replace prior generations before arming another.
- Add a canonical MCP settings-cache reset and real subprocess proofs for disarm and later-work safety.
- Repair the orphan-worker environment so its base interpreter imports both distributions and emits real lifecycle events.

## Outcome

The stdio watchdog still hard-exits on a genuine lost client or confirmed orphan, but normal completion, startup failure, and replacement now cancel the exact active generation. A cancelled Windows waiter checks cancellation again after a simultaneous target signal before invoking `os._exit`, closes held handles, and cannot kill later in-process work.

The exact serial watchdog lane passes 19 tests. Ruff and ty pass on every changed harness file.

## Notes

Vaultspec RAG was attempted first. The shared daemon refused a client-version mismatch; isolated fallback reported an empty local code index, so the required absence/ownership conclusions were corroborated by targeted symbol search and whole-file inspection.

The full serial harness integration run progressed beyond 62 percent and demonstrated normal termination across the repaired watchdog lane, but was stopped for the execution boundary after unrelated failures had already accumulated. No skip, mock, timeout inflation, or sleep-based weakening was introduced.
