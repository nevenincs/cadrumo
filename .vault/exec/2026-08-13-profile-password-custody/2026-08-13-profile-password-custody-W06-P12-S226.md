---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:cf8af87cb49be62fbe9e2312ff37f32e899d130d989e08ffe43d36221960292b'
step_id: 'S226'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S226 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Replace the Windows-only foreign-launcher plant with a platform-neutral real confined-venv launcher swap and prove the canonical path rejects a peer entry point on Windows and POSIX and ## Scope

- `dev/packaging/tests/test_distribution_evidence_emit.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace the Windows-only foreign-launcher plant with a platform-neutral real confined-venv launcher swap and prove the canonical path rejects a peer entry point on Windows and POSIX

## Scope

- `dev/packaging/tests/test_distribution_evidence_emit.py`

## Description

- Replace the Windows-shaped foreign-launcher plant with a platform-neutral swap of the real installed peer `aeat` launcher into the canonical copied-venv `cadrumo-mcp` path.
- Preserve Windows `.exe` bytes unchanged and relocate only the absolute shebang of the real POSIX installed script to the copied confined interpreter.
- Require the canonical-path guard to proceed past confinement and reject the peer specifically for launcher semantic drift.
- Run exact native Windows and WSL/POSIX proofs, the complete native module, the global no-skip/xfail ratchet, Ruff, ty, and independent safety review.

## Outcome

The exact native Windows test passed in 123.87 seconds. After provisioning a lean real WSL environment containing installed `cadrumo` and `cadrumo-harness` launchers, the exact POSIX test passed in 2.47 seconds. The global no-skip/xfail ratchet passed all 25 tests in 35.30 seconds. Ruff and ty passed for the modified module.

The first WSL attempt exhausted `/tmp` while copying an oversized development environment containing CUDA packages, before launcher verification ran. A lean installed environment removed that infrastructure constraint and exposed that copied POSIX scripts retain an absolute source-venv shebang. The final plant rewrites only that first line to the copied venv's real Python and preserves the installed `aeat` script body, allowing the production guard to prove exact-path confinement before rejecting entry-point semantic drift.

## Notes

The complete native module was executed and reported 15 passed and 9 failed outside the S226 exact test. Six failures report that the active installed editable `cadrumo` payload no longer matches a freshly built sealed wheel; three report that valid-client evidence sees stale active installed launcher semantics. These are broader active-environment/cohort-binding failures, not bypasses or failures of the S226 foreign-launcher test, and are retained here for review rather than represented as a green complete module.

No production code, mock, stub, skip, xfail, or platform marker was added. The failed WSL temporary directory was verified by exact path and removed after disk exhaustion; no repository data was affected.
