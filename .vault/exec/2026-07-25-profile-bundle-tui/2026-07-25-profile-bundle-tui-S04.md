---
tags:
  - '#exec'
  - '#profile-bundle-tui'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S04'
related:
  - "[[2026-07-25-profile-bundle-tui-plan]]"
---

# Launch the flow from the bundle command only when required values are missing, --secrets-stdin was not passed, and the capability probe reports a prompt-capable host, then proceed through the unchanged canonical calls, envelope, and notices

## Scope

- `src/cadrumo/entrypoints/cli/_config/_profile_bundle.py`

## Description

- Make the export destination and the import path optional at parse time so an under-specified invocation reaches the command body instead of dying on a click parse error.
- Gate the export launch on all three conditions together: `--secrets-stdin` absent, and either the destination missing or no transport chosen.
- Gate the import launch on the bundle path being absent.
- Route the host decision through the single `interactive_capability` probe, which returns `None` for a non-interactive host so the command keeps its typed refusal rather than re-deriving TTY capability.
- Merge flow answers back over the argv values without overriding anything the operator already supplied, then fall through to the pre-existing canonical path unchanged.
- Leave the export authority call, the import validation gates, the result payloads, and every notice exactly as a fully-specified invocation produces them.

## Outcome

Landed in commit `c4545973f9`. This pass verified the step rather than re-implementing it.

No second export or serialization path was introduced. The flow module performs no serialization, no publication, and no target resolution; it names the export authority only in its module docstring, so the sole portable-export application service established by the W04 `P11.S237` routing remains the only write path. The flow returns two frozen request dataclasses and the command acts on them through the unchanged canonical calls.

Verified green: the 13-test integration run covers the argv-precedence contract directly (`test_scripted_export_run_never_overrides_argv_values` proves an argv-supplied name, destination, and transport all survive a flow run untouched), and the roundtrip proof drives flow-collected answers through the live CLI import verb and the real export authority against real encrypted storage. `uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m integration` reports 351 passed with its single failure isolated to an unrelated peer-owned modelo-390 sequence file carrying uncommitted working-tree edits, so the bundle verbs' documented surface still conforms.

## Notes

The scripted-caller contract is unchanged, but the ADR's recorded consequence stands: the missing-value refusal moved from a click parse error to a typed localized refusal, so a caller matching click's error text sees a changed shape. That is a deliberate, more instructive gate, not a regression.
