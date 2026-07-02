---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S07'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-ports-inversion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-07-02-arch-remediation-ports-inversion-plan placeholders are machine-filled by
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
     The Relocate the justificante repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries and ## Scope

- `src/aeat/domain/justificante/_repository.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Relocate the justificante repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters entries

## Scope

- `src/aeat/domain/justificante/_repository.py`

## Description

- Relocate the concrete justificante metadata repository from the domain package to the persistence adapter; no domain port is declared because the prior port was removed as zero-consumer and no domain-layer caller consumes it.
- Delete the domain repository module and drop it from the domain facade; move the two dedicated repository tests into the adapter tests folder (their subject is now the adapter), which retires their stale domain-to-adapters test edges.
- Sweep the eighteen application and entrypoint consumers to the adapter import home; add the adapter apidocs stub.

## Outcome

- Landed in commit `8b8931473` (tagged `relocation:justificante-repository`). Domain-to-adapters pinned edges fell from 68 to 65; application-to-adapters rose from 340 to 351 (narrow targets, source-module count held at 77).
- Repository roundtrip and consumer suites green against real encrypted SQLite.

## Notes

- INCIDENT: this relocation was committed through an isolated temp index seeded from an earlier HEAD; two peer commits landed before it committed, so the committed tree silently reverted three unrelated files (an mcp annotation coverage guard and its test, and a shared secure-object-records edit). Detected immediately from the commit's file list and remediated in commit `0b3ba12dd` by restoring the peer versions from the working tree. Root cause and the safe alternative (main index plus explicit pathspec, never a temp-index full commit) were recorded as a durable lesson.
