---
tags:
  - '#audit'
  - '#runtime-manager-architecture'
date: '2026-10-05'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:27fe41c8da86087319579253a41e0a9d171cdabc7fa30807c140c2678b1ef4c4'
related:
  - "[[2026-10-04-runtime-manager-architecture-plan]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
---

# `runtime-manager-architecture` audit: `Manager lane checkpoint review`

## Scope

Review of S23, the four-file B5 working-tree change against bcdce3f752, on 2026-10-05. Covers claim ownership from initial S11 admission through restart backoff, launch, readiness, adoption and final outcomes. Other manager Steps and external B4 source changes are outside this checkpoint.

## Findings

### restart-claim-checkpoint | low | S23 passes scoped review and Windows verification

PASS for S23. The supervisor reserves the cross-session start claim before backoff, checks active-session and Quit state while retaining it, and reports changed ownership without starting another runtime. `run_with_permit` accepts the initial S11 guard, validates the pinned root and prevents a pre-readiness retry from contending with its own caller. Readiness, adoption and final outcomes release the guard. Root inspected all four modified files and requested the initial-permit correction before acceptance. Evidence from B5: 121 Windows Rust tests, then 42 affected tests after the final permit-root cleanup, clippy with warnings denied, rustfmt and diff checks passed. Build output is `build/b5-manager-cargo`; commands and environment are in the S23 ledger and conversation tool transcripts. No extra test execution was needed for this review.

### manager-composition-pending | low | this checkpoint does not establish an operational manager

The production `native/manager/src/main.rs` still accepts only `--version` and performs no lifecycle composition. S08/S10/S12/S13 and B4's ordered settle, exact operation counts and record grammar remain open. Windows fixtures establish this Step's claim behavior; Linux compilation and installed-package acceptance are not established here.

### canonical-environment-checkpoint | low | S08 environment subset passes Windows review; composition remains pending

2026-10-05 root review traced the seven-file manager-only change from B2's installed-default resolver through Strict environment construction to the actual fixture child. Developer/authority overrides are refused for managed locations; resolved root and selected-package authority are pinned. A review correction removed retention of raw ambient values: first spawn prepares and caches only canonical filtered output, preserving preparation timing, stable restarts and diagnostic omission. Final affected suite: 85 tests pass; all-target fixture clippy, formatting, release build and diff checks pass using `build/b5-manager-cargo` and the existing B1 generated inputs (executor completions `22caa0`, `7edfba`). No new high or critical finding in this subset. S08 verdict remains PENDING for bounded installed-interpreter probes and the shared Settings projection; no production-manager or Linux acceptance is claimed.

## Recommendations

B5 resumes composition from the open manager Steps after receiving the concrete B1/B2/B4 contracts. Use `run_with_permit` when composing the initial ownership result into the blocking supervisor. Preserve the distinction between S23 completion and product readiness.
