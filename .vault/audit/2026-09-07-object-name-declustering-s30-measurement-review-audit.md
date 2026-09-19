---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:706346b4d9ba0e030925bd95c23914a9a4617a2fe7c6f329fe75d69715b7cc27'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
  - "[[2026-09-07-object-name-declustering-receipt-validity-window-measurement-audit]]"
  - "[[2026-09-07-object-name-declustering-receipt-scope-and-teardown-authority-audit]]"
---

# `object-name-declustering` audit: `S30 receipt validity measurement review`

## Scope

Reviewed W04.P10.S30 against the accepted declustering ADR, the receipt-scope refusal
corpus, the S27-S29 implementation and detector records, and the live Git measurements
recorded in the validity-window audit. The review checked measurement provenance and
arithmetic, the distinction between logical receipt validity and shared-worktree operating
risk, the required plain disposition, and the prohibitions on thresholds, baselines, retry
claims, and commit-time gates.

## Findings

No findings at any severity.

The dirty-tree commands distinguish collapsed status rows, tracked paths, and file-expanded
untracked entries, and separately identify Python paths inside the `src` and `dev` census.
The commit-rate method counts a commit once when its committed path set contains an in-scope
Python file. Its reported rates reproduce from the counts: 51 over six hours is 8.50 per
hour, 134 over twelve is 11.17, and 297 over twenty-four is 12.38. The historical 40-second
expiry, 34-minute failed apply, approximately 65-minute cycle, 14 commits in 90 minutes, and
48 cut-to-apply commits match the receipt-scope audit. The target's 11:57:12 last commit to
the 17:03:31 sample is approximately five hours and six minutes.

The audit does not convert dated observations into an allowlist, threshold, baseline, or
numeric receipt TTL. It correctly states that S27-S29 remove unrelated global inventory
movement from receipt expiry while selected identity, graph, guarded bytes, manifest,
outputs, and gates remain fail-closed. It separately concludes that the observed shared
worktree cannot reliably support a 65-minute live cycle because peer writes and whole-tree
staging can collide with receipt-owned bytes. Requiring an exclusive worktree or a truly
quiesced lane answers S30 without reopening the rejected commit-time-gate remedy.

## Recommendations

No remediation recommendation is required. Preserve the audit's separation between scoped
hash validity and operational isolation; future measurements must remain dated evidence and
must not become a suppression threshold or global expiry rule.
