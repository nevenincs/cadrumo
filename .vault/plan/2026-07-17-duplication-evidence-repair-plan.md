---
tags:
  - '#plan'
  - '#duplication-evidence-repair'
date: '2026-07-17'
modified: '2026-07-17'
tier: L1
related:
  - '[[2026-07-15-cli-authority-verb-conformance-adr]]'
  - '[[2026-07-15-cli-authority-verb-conformance-research]]'
  - '[[2026-07-15-cli-authority-verb-conformance-reference]]'
  - '[[2026-07-16-cli-authority-verb-conformance-duplication-authority-audit]]'
  - '[[2026-07-17-cli-authority-verb-conformance-audit]]'
  - '[[2026-07-15-cli-authority-verb-conformance-plan]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `duplication-evidence-repair` plan

## Description

Repair the duplication measurement instrument so its verdict can be trusted. The duplication-authority audit found the aggregate health report reporting duplication green with no clones found in the same working tree where a direct run observed 65 clone groups at 0.4 percent duplicated lines. The report captures the scanner process result but never inspects the return code or standard error, never carries diagnostic state into its verdict, and never requires a parseable summary before assigning green. On Windows it renders the production path with backslashes, so the scanner can inspect no source files, return no summary, and still be reduced to zero.

Three surfaces independently invoke or parse the clone scanner today: the Just recipe, the duplication module, and the health report. This plan reduces them to one typed platform-neutral runner that owns source selection, command construction, execution, timeout handling, standard output, standard error, return code, parsing, clone records, and availability classification. The report and the Just recipe become consumers of that one authority.

The decision record keeps the clone count advisory, so the goal is honest evidence rather than zero clones. Only a successful, parseable execution that demonstrably observed the production tree and found no clone clusters is an observed zero. A missing executable, a timeout, a non-zero exit, a failed execution, empty evidence, or unparseable output is unavailable evidence and must remain visibly amber rather than collapse into green. An amber verdict carrying a measured count is an acceptable close for this plan.

## Steps

- [x] `S01` - Make dev.audit.duplication the sole owner of the platform-neutral jscpd command, subprocess execution, timeout handling, output parsing, clone records, percentage, diagnostics, and typed availability result; `dev/audit/duplication.py`.
- [x] `S02` - Render every source path through as_posix so Windows and POSIX construct the identical jscpd source selection and no invocation can silently observe zero files; `dev/audit/duplication.py`.
- [x] `S03` - Make the health report consume the typed duplication result and classify zero observed clones as green, observed clones as amber, and unavailable, failed, timed-out, non-zero, or unparseable execution as explicit amber-unavailable; `dev/audit/report.py`.
- [x] `S04` - Delete the duplicate jscpd invocation and parsing path from the health report so the typed runner is the only execution authority; `dev/audit/report.py`.
- [x] `S05` - Replace the shell pipeline with a direct Python duplication runner invocation so Windows and POSIX execute the same authority and retain stdout, stderr, return code, and timeout evidence; `justfile`.
- [x] `S06` - Prove real zero-clone, clone, unavailable executable, non-zero, timeout, stderr, and unparseable outcomes cannot become false green and that report and direct runner render the same typed result; `src/cadrumo/tests/test_dev_audit_report.py`.
- [ ] `S07` - Record an explicit disposition for every observed clone group as cluster-owned, intentional, or advisory residue without treating the count as an elimination mandate; `dev/audit/duplication_dispositions.toml`.
## Parallelization

The runner steps carry hard ordering: the typed runner and its platform-neutral path rendering must exist before the report or the Just recipe can consume it, and the duplicate report path can only be deleted once the report consumes the runner. The false-green proof runs against the finished runner and report together. The clone-group triage step is independent of the runner work and may proceed in parallel with it; its output is a disposition record, not a code change.

The Just recipe is peer-modified territory. Confirm exclusive ownership of it before editing, and land the recipe change in its own explicit-pathspec commit.

## Verification

The runner test suite passes, and each of its cases proves a specific invalid-evidence outcome cannot render green: unavailable executable, non-zero exit, timeout, standard-error diagnostics, and unparseable output each surface as explicit amber-unavailable carrying its diagnostic reason.

The report and a direct runner invocation render the same typed result for the same tree, proving one execution authority rather than two.

The health report shows an honest amber verdict carrying the measured clone count on the current production tree, and shows green only when the runner demonstrably observed the production tree and found zero clone clusters.

Every observed clone group carries an explicit recorded disposition as cluster-owned, intentional, or advisory residue.

A fresh-context honesty review runs against this plan's closure summary before the plan is declared complete.
