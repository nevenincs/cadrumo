---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S183'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run MCP dispatch, identity, input-schema, risk, mutability, and telemetry parity suites

## Scope

- `src/cadrumo/entrypoints/mcp/tests/`

## Description

- Run the MCP suites under an explicit execution-marker selection covering both lanes.
- Read the failing set, then re-run sequentially to separate parallel-worker artefacts from real failures.
- Reduce each surviving failure to its traceback and establish whether the defect is confined to the test harness or reaches a real server process.
- Probe the entrypoint's import chain in a clean interpreter to confirm or refute the production reading.
- Separate owner-surface failures from failures caused by another agent's uncommitted work.

## Outcome

Verdict: FAILED, with two distinct causes, one of them an operator-facing production defect.

Parallel command: `uv run --no-sync pytest -q -rs -p no:cacheprovider -n auto --dist=loadfile --tb=short -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf" src/cadrumo/entrypoints/mcp/tests`.

Collected 279, passed 257, failed 22, skipped 0. Exit line: `22 failed, 257 passed, 6 warnings in 54.60s`, exit code 1. HEAD at run time was `f939f3b473032fd8af27876a4fdd2c65d0d5e102`.

Sequential re-run over the same scope: `13 failed, 267 passed in 529.69s (0:08:49)`, exit code 1. Nine of the parallel failures were worker artefacts of the same registration defect described below; thirteen survive with no workers at all. The serial-marked selection ran one case and it failed. The OS-keychain selection collected nothing.

First cause, owner surface, production defect. Twelve of the thirteen surviving failures raise the same error: the profile-key registry reports that no keys are registered. The chain is direct: the whoami identity builder calls the active-profile health assessor, which lists profile key records, which reads a process-global registry populated only as a side effect of importing the wizard package. A clean interpreter that imports the MCP entrypoint and then reads the registry confirms the wizard package is absent from the loaded modules and the read raises. Every production import of the wizard package is a deferred function-local import inside unrelated command bodies, so nothing on the MCP path ever triggers registration. This is not confined to the harness: the stdio subprocess client test drives a real server process over the wire and receives a tool result with the error flag set and that same message as its text. The shipped MCP identity surface therefore fails for a host that does not happen to have imported the wizard first. The equivalent CLI diagnostics path was exercised end to end through the installed executable and returned a well-formed success envelope, so the defect is confined to the MCP entrypoint.

Second cause, peer work, not owner surface. The remaining failure is the installed-MCP resolution case. It fails because the MCP input-schema build cannot resolve the profile create and profile edit command subtrees, reporting that a wizard results module does not exist. That module is present in the working tree as an untracked file belonging to another agent's in-flight campaign and absent from the installed distribution the oracle drives. This is installed-versus-working-tree skew produced by uncommitted peer work, not a defect in the MCP surface. The parallel-run failure claiming that risk rows reference dead command keys has the same origin and passes sequentially.

## Notes

The semantic code index was degraded for the whole of this wave, reporting itself healthy while carrying roughly a fifth of the tree. Every claim here is bound to a pytest exit line, a traceback, or a clean-interpreter probe.

The first cause is the same root defect recorded against the passphrase and recovery lifecycle Step, where it surfaces as a test-isolation failure. Here it surfaces through a real subprocess server, which is the stronger evidence and the reason this Step is reported as a product failure rather than a harness one.

The registry is a process-global whose only population point is a side-effecting import that the lazy-import policy deliberately defers. Any durable fix has to give the registry an initialisation point the entrypoints actually reach, rather than adding another test-fixture import.
