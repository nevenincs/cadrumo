---
tags:
  - '#exec'
  - '#duplication-evidence-repair'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-17-duplication-evidence-repair-plan]]"
---

# Delete the duplicate jscpd invocation and parsing path from the health report so the typed runner is the only execution authority

## Scope

- `dev/audit/report.py`

## Description

- Delete the second scanner command the health report constructed for itself.
- Delete the report's own output-parsing path.
- Leave the typed runner as the only surface in the tree that executes or parses the scanner.

## Outcome

`dev/audit/report.py` no longer builds a scanner command or parses scanner output. The duplicate invocation is gone, so the measurement instrument is no longer an instance of the duplication it measures, and there is exactly one execution authority to audit.

The landing commit is `4cd774bdde`. A standing gate, `test_only_one_jscpd_invocation_exists_in_the_tree`, now enforces the single-owner property across every surface that can execute a command.

## Notes

The duplicate path was the direct cause of the divergent verdicts: the report's private command and the build recipe's pipeline were two independently-drifting specifications of the same scan, and only one of them was ever corrected at a time.

The single-owner gate initially did not scan the build recipe, leaving a second pinned scanner version outside its reach. That gap was raised by the plan's close honesty review and has since been closed; the gate now covers the build recipe alongside the Python tree.

This record was authored on 2026-07-24, after the work landed, to close the missing-execution-record finding raised by the same review.
