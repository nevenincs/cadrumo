---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:ae323f1dc424eb36923a587a270aeb50ae336370b73610ce3ad46ed9069b4fdb'
step_id: 'S274'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Resolve the two broken layered contracts with their owning campaigns, without widening the ignore list

## Scope

- `.importlinter`

## Description

- Re-run the layered contracts at HEAD rather than inheriting the reported
  breakage.
- Confirm the resolution did not come from widening the ignore list, which the
  row forbids.

## Outcome

SATISFIED, and resolved by the owning campaigns rather than here - which is
what the row asked for.

The close review measured three contracts kept and two broken, with roughly ten
violating edges: three domain-to-application edges from a bucket payload-version
test, one from profile registration, two from a sandbox notice into adapters
persistence, and four TUI test modules importing entrypoints. It attributed
every one to another campaign and absorbed none, correctly.

At HEAD all five contracts are evaluated and all five are KEPT. Measured by
running the real linter, not by reading a report: the layering dimension returns
`all 5 of 5 import-linter contract(s) kept`.

The forbidden remedy was not used. The row bars resolving these by widening the
ignore list, because that is what produced the stale entries that aborted the
whole run in the first place. Two independent checks say it was not: every
contract still declares `unmatched_ignore_imports_alerting = error`, so a
widened ignore that matched nothing would abort the run rather than silence a
violation; and the sibling gate asserting every ignore-listed module resolves on
disk remains green, so no entry was added pointing at a module that does not
exist. The violating edges were removed, not exempted.

Gates at HEAD `a4ccd70c3e16898587cc74f33f40b2cdcf7dce45`:

- The live layering dimension evaluates 5 of 5 declared contracts and reports
  all kept.
- `uv run --no-sync pytest src/cadrumo/tests/test_dev_audit_report.py -n0
  -k layering` collected 2 cases and exited `2 passed`, including the floor
  asserting evaluated equals declared.

## Notes

Worth stating why this row could not have been closed on the close review's
numbers. Those numbers were correct when taken and describe a tree that no
longer exists; four campaigns have landed since. Had this been closed by
reading the review, it would have reported two broken contracts that are not
broken, and had it been closed by reading only the exit code it would have
missed that the run now evaluates all five rather than aborting. The
distinction between those two failure modes is the sibling row's whole subject.
