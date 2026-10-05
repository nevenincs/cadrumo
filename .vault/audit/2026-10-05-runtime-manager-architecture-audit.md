---
tags:
  - '#audit'
  - '#runtime-manager-architecture'
date: '2026-10-05'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:639f688c28c992ad86b4f6bd21f473a6417b9064d22142a4a1a1afa7f4d2e3f8'
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

## Recommendations

B5 resumes composition from the open manager Steps after receiving the concrete B1/B2/B4 contracts. Use `run_with_permit` when composing the initial ownership result into the blocking supervisor. Preserve the distinction between S23 completion and product readiness.
