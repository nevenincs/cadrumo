---
tags:
  - '#audit'
  - '#honest-all-green'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:e9f6ea6a67c18a5da7eadee8a99f88b5556193e9477c6748f174bb31d2314728'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
  - "[[2026-07-14-honest-all-green-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace honest-all-green with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `honest-all-green` audit: `P06 import-boundary review`

## Scope

<!-- What was audited and why -->

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### P06 import-boundary review | {level} | {summary}

     followed by a paragraph carrying the detail. P06 import-boundary review is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### sync-run-repository-nullability | high | the new application port is still optional at its required write site

`capture_filed_data_bulk` rejects a missing `sync_run_repository` for a non-preview capture, but the later `record_sync_run` call receives the unchanged `SyncRunRecordRepositoryProtocol | None` variable. Targeted `basedpyright` therefore rejects `src/cadrumo/application/live/_filed_data_capture.py:901` because the writer requires a non-optional protocol. This is P06-owned and prevents the strict type lane from reaching green, despite the focused real-stack behavior tests passing. The concrete `SyncRunRecordRepository` remains adapter-owned, the application imports only `SyncRunRecordRepositoryProtocol`, and the CLI composition root supplies the concrete adapter; no persistence implementation leaked back into application.

#### Resolution

The non-preview preflight remains before any capture write, and the post-preview persistence boundary now repeats the missing-port refusal immediately before finalization and `record_sync_run`. That second guard narrows the value to `SyncRunRecordRepositoryProtocol` at the required call without a cast or assertion. Targeted `basedpyright` reports zero errors; the real sync-record and supported filed-capture suite reports 11 passed; scoped Ruff and `check-imports` are green.

#### Closure disposition

Resolved. Independent review confirms the second refusal occurs after the preview return and before either finalization or the provenance write, so a persisted capture cannot reach `record_sync_run` with a missing port. The exact targeted `basedpyright` command reports zero errors, and the real encrypted sync-run persistence suite passes 10 tests. The remediation retains the concrete repository in the persistence adapter and construction at the CLI composition root.

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->

- Resolve the non-preview guard into a non-optional local before `record_sync_run`, then rerun the targeted type check and the existing real persistence and filed-capture suites. Retain concrete construction exclusively at the entrypoint composition root.
