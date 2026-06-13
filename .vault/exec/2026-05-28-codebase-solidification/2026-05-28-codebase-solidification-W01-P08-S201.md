---
step_id: S201
date: 2026-05-28
modified: '2026-05-28'
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P08.S201

Replaced `**kwargs: Any` in `src/aeat/tests/cli_runner.py`:

- Added `ClickInvokeKwargs(TypedDict, total=False)` covering `env`, `color`, `catch_exceptions`, `input` (Click invoke surface).
- Changed `invoke_cached_cli(args, **kwargs: Any)` → `invoke_cached_cli(args, **kwargs: Unpack[ClickInvokeKwargs])`.
- Unknown kwargs are now a static type error at call sites.

Commit: `491d6af66`
