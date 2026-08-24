---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:72f48a49e4ba509b0e519e1b09af0f72968901473fdd2b87836c7f535b0dea4b'
step_id: 'S226'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Replace the Windows-only foreign-launcher plant with a platform-neutral real confined-venv launcher swap and prove the canonical path rejects a peer entry point on Windows and POSIX

## Scope

- `dev/packaging/tests/test_distribution_evidence_emit.py`

## Description

- Replace the Windows-shaped foreign-launcher plant with a platform-neutral swap of the real installed peer `aeat` launcher into the canonical copied-venv `cadrumo-mcp` path.
- Preserve Windows `.exe` bytes unchanged and relocate only the absolute shebang of the real POSIX installed script to the copied confined interpreter.
- Require the canonical-path guard to proceed past confinement and reject the peer specifically for launcher semantic drift.
- Run exact native Windows and WSL/POSIX proofs, the complete native module, the global no-skip/xfail ratchet, Ruff, ty, and independent safety review.

## Outcome

The final exact native Windows test passed in 90.69 seconds. After provisioning a lean real WSL environment containing installed `cadrumo` and `cadrumo-harness` launchers, the final exact POSIX test passed in 4.12 seconds. The global no-skip/xfail ratchet passed all 25 tests in 35.30 seconds. Ruff and ty passed for the modified module.

The first WSL attempt exhausted `/tmp` while copying an oversized development environment containing CUDA packages, before launcher verification ran. A lean installed environment removed that infrastructure constraint and exposed that copied POSIX scripts retain an absolute source-venv shebang. The final plant rewrites only that first line to the copied venv's real Python and preserves the installed `aeat` script body, allowing the production guard to prove exact-path confinement before rejecting entry-point semantic drift.

## Notes

The complete native module was executed and reported 15 passed and 9 failed outside the S226 exact test. Six failures report that the active installed editable `cadrumo` payload no longer matches a freshly built sealed wheel; three report that valid-client evidence sees stale active installed launcher semantics. These are broader active-environment/cohort-binding failures, not bypasses or failures of the S226 foreign-launcher test, and are retained here for review rather than represented as a green complete module.

No production code, mock, stub, skip, xfail, or platform marker was added. The failed WSL temporary directory was verified by exact path and removed after disk exhaustion; no repository data was affected.

Independent review identified one LOW anti-tautology gap in the first POSIX version: it relocated the first line without proving that line was the installed peer's absolute source-environment Python shebang. The final witness proves the shebang marker, absolute path, strict interpreter resolution, and equality with the source server's owning Python before relocation.
