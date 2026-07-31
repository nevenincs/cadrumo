---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:38d32f5de5bcb348c1714d605de2ed3644354413da315bb1997cc9f9db3db218'
step_id: 'S17'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Implement the check CLI mode that fails with the page, sequence id, frame index, argv, differing_paths or unified diff, and the exact refresh invocation

## Scope

- `dev/docs/sequences/__main__.py`

## Description

- Implement `check_sequences` — THE engine check function both future gate surfaces (the Sphinx builder-inited hook and the dev-docs pytest gate, plan W03.P08) call, so a divergence reds every surface through one execution-and-comparison path.
- For each discovered sequence: read the committed golden (a missing or hand-corrupted golden is a named problem carrying the exact refresh invocation), re-execute in a fresh hermetic sandbox, and run the shared `check_transcript` tier (golden comparison plus live `@expect` evaluation).
- Implement the `check` CLI mode: exit 0 with a clean summary, exit 1 printing every FAIL line — page, sequence id, frame index, argv, post-mask differing paths or unified text diff — and a closing remedy line with the exact scoped refresh invocation.
- Cover the mode with real tests: clean pass after a real refresh, golden-mutation drift naming the frame and path and remedy, missing-golden refusal, and a direct `check_sequences` call proving the CLI wraps the same function the gates will.

## Outcome

A wrong writeup, a renamed verb, a changed output shape, or a CLI regression fails the check with a named sequence, frame, and diff, plus the one command that updates the golden — the ADR's operator-facing failure contract, end to end.

## Notes

No incidents.
