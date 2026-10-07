---
tags:
  - '#audit'
  - '#runtime-file-access-performance'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:36809bb304f17219073aeefb4582d10f9af6214f135cab799c513fdb14747169'
related:
  - "[[2026-10-07-runtime-file-access-performance-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace runtime-file-access-performance with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

# `runtime-file-access-performance` audit: `Runtime file access and deferred document engines`

## Scope

## Scope

Review of completed S01 and S02 under the approved runtime-file-access-performance plan, including the diagnostic guidance correction in a42e9f838a. S04 binary rebuilding and artifact verification remain pending and will be appended here. Reviewed committed production changes in 9df7d1079d and ce897fe317 against their parent states, plus the shared working-tree interactions covered by the recorded full quality gates.

Accepted TUI D6 requires canonical strict fixed-point operation bindings; the published-authority decision requires digest-bound, format/generation admission and selective hydration; interpreter-foundation and runtime-manager decisions retain package integrity, isolated startup and owned processes. Equivalent deferred imports introduce no new public contracts, persisted schema or cache.

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### Runtime file access and deferred document engines | {level} | {summary}

     followed by a paragraph carrying the detail. Runtime file access and deferred document engines is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### operation-engine-loading | low | Registration imported engines that only document operations use

Resolved in S02. Registration reached openpyxl/numpy through local observations, XLSX provider imports and workbook materializer composition; PDF extraction/container imports reached pdfplumber/pdfminer, PDFium and pikepdf. The owning functions now import their existing engines when the operation executes. Optional-extra checks and malformed-file refusals remain in place. Tests exercise real PDF extraction, XLSX validation/formula refusal and summary generation/verification. A fresh isolated production-registry test proves engines are absent from sys.modules while the public contract set exists. Matched full public catalogues retain 266 definitions and digest 615d08f82346ec538ddd91e7290b2b561e6add21ab586c5f52710ab5be36bc10.

### io-measurement-coverage | low | File API counts must retain their measurement scope

Python traces report open attempts and canonical caller locations, not bytes or physical media activity. Native counts report successful ReadFile transfers separately from EOF and unsuccessful opens. Normal source-registry open attempts fell from 3121 to 2735. Observed native bytecode imports fell from 3156 to 2764 successful reads and 49446890 to 44258297 reported bytes. Captures lack process-exit records; they establish observed import/admission scope, not complete process-lifetime physical disk I/O. Incomplete comparison captures were excluded from the comparison. Five diagnostic tests cover real repeated reads and missing opens, native accounting/locale/PID filtering, malformed length refusal, audit-hook reuse and exclusion of private SystemExit text.

### authority-admission | low | The measured registry read is one integrity hash

The 117620736-byte authority required 1796 successful native ReadFile events and 117620836 transferred bytes during the observed admission. Multiple CreateFile events reflect metadata/opened SQLite connections, not repeated full scans. Publication remains the structural validation boundary; runtime retains digest, format and generation guards and selective indexed hydration. Six alternating samples per buffer size proved identical hashes: existing 64 KiB median 0.08752 wall seconds/0.08594 CPU seconds, 256 KiB 0.09639/0.09375, 1 MiB 0.10227/0.10938. Larger buffers reduce read calls but cost more time, so no buffer or cache change was made.

### capture-environment-exposure | high | A raw process-start record exposed credentials in diagnostic output

One tool output inadvertently included process-start environment records containing credentials. This is an actual exposure; deleting files cannot remove that transcript output. Raw PML/CSV exports and the process-record JSON were removed; retained evidence contains selected file operations only. The diagnostic instructions now require target file-operation filtering before exporting or inspecting. Rotation of exposed credentials remains outside this repository change. No credential values enter the tracked code or audit.

### completed-source-verification | low | Source corrections pass relevant integration and quality checks

PASS for the completed source changes, with the credential-rotation follow-up above retained separately. Real extraction/spreadsheet/PDF writer and verifier, schema parity, operation composition, fresh-process registration, runtime CLI and headless native startup/identity/interference checks passed across focused runs. The recorded full format/style/type checks passed. A complete import check against an unchanged before/after tree passed with 4522 loaded modules, 15 kept contracts and zero hard findings: var/storage/development/.logs/test-runs/2026-10-07/20261007T131850.700218Z-check-import-boundaries-32264-369c86d0/artifacts/import-health.json. A prior run was invalidated by source changes and was not used as passing evidence. The later diagnostic-only guidance change passes format and changes no import/type behavior. Installed-artifact verification is PENDING under S04.

## Recommendations

## Recommendations

Rotate credentials exposed by the process-environment output. Keep capture filtering before export/inspection and retain no raw process-environment records.

Complete S04 against the rebuilt Windows package and append its artifact identity, build timing and native runtime measurements here. Source/development timings cannot stand in for the delivered executable.

No new application cache is justified by the measured I/O: imports are predominantly unique and the full authority pass is its integrity admission. Preserve existing OS/build caches and authority-reader ownership. Any later cache opportunity must first establish repeated same-input work and remain bounded by the owning immutable contract/generation; do not retain private request data or bypass freshness.
