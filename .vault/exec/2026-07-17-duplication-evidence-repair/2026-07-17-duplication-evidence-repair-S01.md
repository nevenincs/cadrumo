---
tags:
  - '#exec'
  - '#duplication-evidence-repair'
date: '2026-07-24'
modified: '2026-07-25'
body_hash: 'sha256:9d1c4c8d02a9a17f77fc07b1cfa02399de7bb3c46c958d4a3b3df312e1f1ec98'
step_id: 'S01'
related:
  - "[[2026-07-17-duplication-evidence-repair-plan]]"
---

# Make dev.audit.duplication the sole owner of the platform-neutral jscpd command, subprocess execution, timeout handling, output parsing, clone records, percentage, diagnostics, and typed availability result

## Scope

- `dev/audit/duplication.py`

## Description

- Move the whole clone measurement behind one typed three-state result in `dev/audit/duplication.py`.
- Own the scanner command construction, subprocess execution, and timeout handling in that module alone.
- Own standard-output parsing, clone records, duplicated-line percentage, and standard-error diagnostics there.
- Classify the outcome as observed-zero, clones, or unavailable, and carry the diagnostic reason on the unavailable arm.
- Require a demonstrated non-zero analysed-file count before an observed zero can be constructed.

## Outcome

`dev/audit/duplication.py` is the single execution and parsing authority for the clone scanner. The typed result distinguishes an observed zero, proven by an analysed-file count greater than zero, from an unavailable execution carrying its reason. A missing executable, a timeout, a non-zero exit, empty evidence, or unparseable output can no longer be reduced to a zero clone count, because the zero arm cannot be constructed without evidence that files were inspected.

The landing commit is `4cd774bdde`, which grew this module by 366 lines.

## Notes

The false-green defect this step repairs was structural, not incidental: the previous code captured the scanner process result but never inspected its return code or standard error, so an execution that inspected no files at all parsed as a clean zero.

This record was authored on 2026-07-24, after the work landed, to close the missing-execution-record finding raised by the plan's fresh-context close honesty review. The evidence is the named commit and the module at HEAD, not a contemporaneous log.
