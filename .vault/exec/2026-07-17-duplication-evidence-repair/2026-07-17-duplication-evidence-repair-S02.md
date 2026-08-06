---
tags:
  - '#exec'
  - '#duplication-evidence-repair'
date: '2026-07-24'
modified: '2026-07-25'
body_hash: 'sha256:f44cb7435b6bb59e18c626cc37ddd385511e1baa01edc5309743055b4d1bcba7'
step_id: 'S02'
related:
  - "[[2026-07-17-duplication-evidence-repair-plan]]"
---

# Render every source path through as_posix so Windows and POSIX construct the identical jscpd source selection and no invocation can silently observe zero files

## Scope

- `dev/audit/duplication.py`

## Description

- Render every source path handed to the scanner through the POSIX form rather than the platform-native string.
- Make Windows and POSIX construct a byte-identical scanner source selection.

## Outcome

The production source path is passed to the scanner in POSIX form, so the Windows run selects the same files as the POSIX run. This closes the precise mechanism behind the false green: the previous code passed the platform-native rendering, which on Windows produced a backslash path the scanner matched zero files against, emitting only a timing line and exiting zero.

Combined with the analysed-file-count requirement from the sibling runner step, an invocation that observes no files is now classified unavailable rather than clean. The landing commit is `4cd774bdde`; a follow-up, `7de67bb49a`, replaced the shared encoding constant with a module-local one in the same runner.

## Notes

The platform dependence made the defect invisible on POSIX continuous integration while reporting a false green on the operator's Windows workstation, which is where the contradiction between the health report and a direct scanner run was first observed.

This record was authored on 2026-07-24, after the work landed, to close the missing-execution-record finding raised by the plan's fresh-context close honesty review.
