---
step_id: S573
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W10.P40.S573 — _render.py os.environ cache-key allowlist doc

## Outcome

Added inline allowlist rationale comment in `src/aeat/core/i18n/_render.py` at line 145
where `_output_language_cache_key()` reads `os.environ.get(name)` in a loop over
`_OUTPUT_LANGUAGE_KEY_ENV_VARS` (which includes AEAT-prefixed keys).

The comment explains: these reads compute a cache-key signature only, not a settings
value. Building a full Settings instance on every `tr()` call costs ~100 Settings
constructions per `--help` render (the disaster-ADR Ruling 4 regression). The raw
env vars are sampled to detect change; a cache miss still invokes `load_settings()`
normally inside `_cached_output_language`.

The AST-level scanner in `test_settings_single_surface_invariant.py` does not detect
this pattern (loop-based iteration over the names tuple), so no allowlist entry
is added. Adding a stale allowlist entry would trigger the bitrot test.

## Grep post-condition

No structural changes to scanner results. Inline rationale document added.

## Commit

`5cc2fffd6`
