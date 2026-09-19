---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:be5a41f4006e5fcc4c558ef242ba4ace04ce2899feceef808312ccbc2a54c371'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# `profile-password-custody` audit: `S226 foreign launcher review`

## Scope

Reviewed only W06.P12.S226 against the accepted custody rollup decision, the corrected S223 close audit, the S226 plan and execution record, the complete `test_exact_path_foreign_launcher_is_refused` implementation, and production `assert_installed_console_entry_point` and `installed_python_for_cli` behavior.

The Windows branch copies the real installed `aeat.exe` bytes unchanged into the canonical copied-environment `cadrumo-mcp.exe` path. The POSIX branch retains the real installed `aeat` script body and changes the interpreter line to the copied environment's resolved Python so production exact-path confinement succeeds before launcher-body comparison rejects the peer specifically as semantic drift. This is an honest adaptation of an absolute installed-script shebang after relocating the environment; it does not synthesize peer entry-point semantics.

Recorded validation was considered as evidence: the exact native test passed once, the exact WSL/POSIX test passed once in the lean real installed environment, the global no-skip/xfail ratchet passed 25 tests, and Ruff and ty were clean. The initial WSL `/tmp` exhaustion occurred before launcher validation and is infrastructure-only. The complete native module's six sealed-wheel payload mismatches and three stale valid-client launcher mismatches are active-installed-environment/cohort failures outside the changed exact test. They demonstrate the production binding checks refusing drift and are not caused by, nor bypasses of, S226; they prevent representing the complete module as green but do not block this narrowly scoped platform-neutral witness.

## Findings

### posix-source-shebang-proof | low | The POSIX plant does not verify the discarded line is an absolute shebang

The POSIX branch binds `_original_shebang` but never inspects it, and `assert separator` proves only that the installed peer file contains a newline. The diagnostic claims the real peer launcher carries a shebang, while the code would also discard an arbitrary first line and manufacture a confined shebang. The real lean WSL environment makes the observed run honest, and the remainder of the real `aeat` script body is preserved, so this does not expose a production bypass or invalidate the cross-platform result. It is nevertheless a small anti-tautology gap against S226's explicit promise to relocate only an absolute shebang.

## Recommendations

Before closing S226 without a carry-forward, assert that `_original_shebang` begins with `#!`, resolves to the source environment's real Python, and is absolute, then retain the existing exact Windows and WSL/POSIX proofs. No production change is indicated. Subject to that LOW witness fix, the platform-neutral launcher swap is a PASS with no critical, high, or medium findings.

## Resolution

### posix-source-shebang-proof-resolved | low | The source shebang proof now binds the real peer launcher to its environment

Resolved in the current S226 diff. The POSIX branch now proves the first line exists, begins with `#!`, decodes to an absolute path, resolves strictly, and equals the source `cadrumo-mcp` environment's resolved Python before replacing only that line with the copied environment's resolved Python. The real installed `aeat` body and mode remain unchanged. This closes the anti-tautology gap without weakening the production semantic-drift assertion.

Final recorded validation after the resolution is one exact native Windows pass in 90.69 seconds, one exact WSL/POSIX pass in 4.12 seconds, and clean Ruff and ty results. Final disposition: PASS. No critical, high, medium, or unresolved low findings remain for S226.
