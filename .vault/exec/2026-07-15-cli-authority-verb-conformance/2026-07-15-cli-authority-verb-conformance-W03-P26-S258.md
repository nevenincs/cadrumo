---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S258'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
  - "[[2026-07-15-cli-authority-verb-conformance-adr]]"
---

# Make dev.audit.duplication the sole owner of the platform-neutral jscpd command, subprocess execution, timeout handling, output parsing, clone records, percentage, diagnostics, and typed availability result

## Scope

- `dev/audit/duplication.py`

## Description

- Establish that this step duplicates a step already closed under a rescoped successor plan rather than treating it as open work.
- Re-run the single-owner gate at the current commit rather than trusting its recorded result.
- Confirm the gate's scan reaches beyond the development subtree, which is what an earlier close review found it did not.

## Outcome

Already satisfied. Closed as verified rather than re-implemented.

This step's action text is word-for-word identical to the first step of the duplication-evidence-repair plan, a rescoped successor carved out of this campaign and carrying its own feature tag. That step is closed and its work landed in the repair commit. Re-implementing here would have produced a second duplication authority inside the campaign whose entire purpose is to eliminate the second duplication authority.

Verified at the current commit rather than accepted on the checkbox. The runner owns the platform-neutral command, the subprocess execution, the timeout, the parsing, the clone records, the percentage, the diagnostics, and the typed availability result, and the single-owner gate passes as part of a 22-test run over the duplication module.

One earlier gap is independently confirmed closed. A close review of the successor plan found the single-owner gate scanning only Python files under the development tree, so a scanner reintroduced in the build recipe, a shell script, the source tree, or the packaging tree would have passed silently, and the gate therefore proved less than its docstring claimed. It now enumerates the whole git-tracked tree, narrows to files that can actually execute a command, and excludes Python docstrings from the search so a test module can quote the invocation in prose without needing its own exemption entry. That is the correct shape: the exemption set stays at two named files instead of growing with every module that documents what it exercises.

## Notes

Semantic CODE search was degraded and reported itself healthy: 188 indexed sections against roughly 4546 tracked files, an available status, and an empty degraded-reasons list. Two deliberately unrelated probes returned the same file at similarity around 0.001, and the clone-runner module did not appear in a probe naming it directly. Code discovery was by targeted search and direct reads.

The VAULT index was healthy at 16121 documents and is what found this duplication. A vault search for the duplication authority surfaced the successor plan and its close review immediately; without it this step would have been re-implemented as open work.
