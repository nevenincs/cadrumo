---
tags:
  - '#audit'
  - '#cli-storage-text-formatting'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:1da3c2e0982fa1a57a37959e8ec5d2dd453dbb2916b93863f4dfd0656daf6724'
related: []
---

# `cli-storage-text-formatting` audit: `Storage text output formatting`

## Scope

Audited the in-flight text-rendering changes for all five `aeat config storage`
verbs against the accepted shared-output boundary and the reported requirement
that informational output be visually parseable. The review covered the
production diff in `_storage_cli.py`, the regression diff in
`test_config_storage_surface.py`, and the unchanged-line behavior of
`_emit_envelope`. Focused integration verification passed all 20 tests in the
storage CLI surface module. The default pytest profile was also checked but
deselected the module because these tests carry the integration marker, so that
zero-test run was not treated as evidence.

## Findings

### notice-wrapping | medium | Informational notices remain single unbounded lines

`_notice_lines` prepends a severity label but emits each complete localized
message as one physical line. The standing relocation advisory rendered as a
260-character line in the active Spanish locale. Because `_emit_envelope`
preserves the supplied text lines unchanged, normal-width terminals must wrap
that line at arbitrary columns with no hanging indent or visual relationship to
the `Info:` label. The tab-delimited records are improved, but the long
informational text that prompted the readability complaint remains difficult to
scan.

### text-regression-coverage | low | Tests do not prove the full multiline storage text contract

The new text assertions exercise `list`, `show`, and the no-op `init` path, but
do not exercise either healthy or drifted text output from `check`, and do not
exercise successful text output from `reclaim`. The `list` and `init`
assertions are largely substring checks: they would still pass if headings,
records, paths, and notices were collapsed into an unreadable physical-line
layout, provided tabs were absent. The focused module therefore passes while
leaving the remaining changed text branches and the reported visual topology
unprotected.

## Recommendations

- For `notice-wrapping`, render notices to a bounded width with a stable hanging
  indent beneath the localized severity label, while continuing to pass the
  resulting lines through `_emit_envelope` and leaving the structured notice
  envelope unchanged.
- For `text-regression-coverage`, add real CLI tests for healthy and drifted
  `check` output and successful `reclaim` output. Assert physical line
  boundaries, continuation indentation, and a reasonable maximum line width so
  the gate fails when prose is collapsed or returned to record-like output.

## Resolution log

### 2026-08-10 | resolved | notice-wrapping

Re-review confirmed that `_notice_lines` now uses a 96-column `TextWrapper`
with the severity prefix as the initial indent and an equal-width hanging
indent on continuation lines. The active Spanish relocation advisory rendered
as physical lines of 79, 96, and 95 characters after the intentional blank
separator; both continuation lines began with the six spaces corresponding to
`Info: `. The original medium finding is closed.

### 2026-08-10 | resolved | text-regression-coverage

Re-review confirmed real text-mode coverage for the richer drifted `check`
branch and successful `reclaim`, in addition to the existing `list`, `show`, and
no-op `init` coverage. The `list` regression now requires multiple notice lines,
caps every rendered notice line at 96 columns, and asserts hanging indentation
on every continuation. The focused integration module passed all 22 tests, so
the original low finding is closed. No audit finding remains open.
