---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S21'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace conformance-cli with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S21 and 2026-07-27-conformance-cli-plan placeholders are machine-filled by
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
     The wire a conformance recipe invoking python -m dev.registry.conformance report and audit into the task runner and ## Scope

- `justfile` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# wire a conformance recipe invoking python -m dev.registry.conformance report and audit into the task runner

## Scope

- `justfile`

## Description

- Located the Advisory audits section in `justfile` (lines 479-527) — the correct placement block between `audit-health-report-json` and the Documentation section separator.
- Confirmed no peer WIP on `justfile` via `git diff -- justfile` (no output).
- Added `audit-registry-conformance` recipe with a two-line body: `python -m dev.registry.conformance report` then `python -m dev.registry.conformance audit`. Added an inline comment explaining screen posture and directing readers to `audit --check` for gating.
- Committed with explicit pathspec: `0158ac6c3c -- justfile`.

## Outcome

Recipe added and committed. It matches the shape of sibling advisory audit recipes (`@uv run --no-sync python -m dev.XXX`). No logic in the justfile — thin invocation only.

Verified recipe collects correctly:

```
audit-registry-conformance:
    @uv run --no-sync python -m dev.registry.conformance report
    @uv run --no-sync python -m dev.registry.conformance audit
```

Commit SHA: `0158ac6c3c`.

## Notes

The recipe exits 0 always (both `report` and `audit` without `--check` are screen-posture verbs). The gating exit is exclusively in `audit --check`, exercised by the CI integration test added in S19.
