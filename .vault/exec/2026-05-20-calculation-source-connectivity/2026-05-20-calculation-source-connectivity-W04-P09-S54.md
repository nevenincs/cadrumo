---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S54'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace calculation-source-connectivity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S54 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Run feature surface quality gate for source mesh touched files and ## Scope

- `.agents/skills/feature-surface-gate/SKILL.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run feature surface quality gate for source mesh touched files

## Scope

- `.agents/skills/feature-surface-gate/SKILL.md`

## Description

- Run the feature-surface quality gate over the source-mesh touched files as a process step (not code): ruff format and check, ty type check, collect-only, and the targeted persistence/roundtrip and fingerprint test suites.

## Outcome

- ruff format: all touched files unchanged; ruff check: all checks passed.
- ty check on the six touched production modules: all checks passed.
- Persistence/roundtrip suite (source-mesh revision roundtrip, calculation repository roundtrip, ledger-filing-evidence roundtrip, domain-filing anti-tautology and secure-storage roundtrips, calculation-revision, domain-modelos secure-storage roundtrip): 39 passed.
- Registry-free invoice-fingerprint unit tests: 3 passed.
- Locale scaffold check: all four catalogues ok.
- Collect-only on the touched packages: clean (0 collection errors).

## Notes

Whole-tree collect-only surfaced two PRE-EXISTING collection errors unrelated to this feature: the MCP tests (`entrypoints/mcp/tests`) fail with `ModuleNotFoundError: No module named 'pywintypes'`, an absent-environment-dependency issue, not this diff. The S52 invoice-staleness integration tests cannot run green in the current worktree because the full-registry validation is red on uncommitted modelo-131 revision 2025 peer WIP; this is peer churn, not this feature's surface (the untouched existing approval test fails identically), and the S52 fingerprint mechanism is covered by the registry-free unit tests. Reported the modelo-131 blocker to the coordinator.
