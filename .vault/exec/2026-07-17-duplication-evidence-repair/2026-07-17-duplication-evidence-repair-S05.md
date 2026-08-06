---
tags:
  - '#exec'
  - '#duplication-evidence-repair'
date: '2026-07-24'
modified: '2026-07-25'
body_hash: 'sha256:0e665c72df146ffdea6986c127b1248192801ea3ee57450371c17c5783add71b'
step_id: 'S05'
related:
  - "[[2026-07-17-duplication-evidence-repair-plan]]"
---

# Replace the shell pipeline with a direct Python duplication runner invocation so Windows and POSIX execute the same authority and retain stdout, stderr, return code, and timeout evidence

## Scope

- `justfile`

## Description

- Replace the build recipe's shell pipeline with a direct invocation of the Python duplication runner.
- Make Windows and POSIX execute the same authority from the recipe.
- Retain standard output, standard error, return code, and timeout evidence through the runner rather than discarding it in a pipe.

## Outcome

The duplication recipe invokes the typed runner directly, so an operator running it by hand and the health report reach the same verdict from the same code. The shell pipeline that previously discarded the return code and standard error is gone, and the diagnostic evidence the runner needs to classify availability survives the call.

The recipe change landed in `4cd774bdde` and was adjusted again in `3f07664375` when the dispositions coverage gate landed.

## Notes

The build recipe is peer-modified territory, so the plan required confirming exclusive ownership before editing it and landing the change under an explicit pathspec. Both recipe edits are narrow, at four and two lines respectively.

This record was authored on 2026-07-24, after the work landed, to close the missing-execution-record finding raised by the plan's fresh-context close honesty review.
