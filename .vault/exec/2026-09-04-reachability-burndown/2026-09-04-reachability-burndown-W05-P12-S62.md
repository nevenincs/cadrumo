---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:06c8b1f6a1a1bb46f58837fa8272f8a038480dbee5c04730ad83d48209939fce'
step_id: 'S62'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Wire two confirmed findings instead of classifying them: give the colour rule an optional stream probe so it can serve stderr, and have the localised Click exception override consult it with the stderr probe rather than Click's own show_color, which makes NO_COLOR and CADRUMO_FORCE_COLOR reach error output for the first time while an explicit show_color still wins; and emit the collaboration package-encrypted event from the review-package encrypt command against the bucket event history, so a package leaving the bucket is now recorded where the encrypt previously succeeded silently

## Scope

- `src/cadrumo/entrypoints/cli/_tty.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_tty.py`
- `M` `src/cadrumo/entrypoints/cli/_framework_localisation.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_review_package_cli.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/cli` -> `pass`
- `verify:` `CADRUMO_FORCE_COLOR=1` and `NO_COLOR=1` through the override -> `True` / `False`

## Notes

The colour fix was checked for a regression before landing: the override writes
to stderr while `should_use_color` tested stdout, so wiring it naively would
have dropped colour whenever stdout is piped and stderr is a terminal. The
helper gained an optional `stream_is_tty` probe and the call site passes
`stderr_is_tty`.

Two symbols leave the decision backlog by being wired rather than reclassified:
`should_use_color` and `emit_collab_package_encrypted_event`.
