---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:54b47f7ca31d477d0ccfdb612bb45197e1a4a8a5d960f80d2907192a00cd0543'
step_id: 'S33'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Extract the shared oracle fixture scaffolding while keeping each test body separate, so a scenario change lands once

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Description

- Extract the revision resolution both income-chain oracles depend on into one shared module.
- Keep the invoice rows and expected figures duplicated in each oracle, since they differ by design.

## Outcome

Landed as commit `9e612476b3`, "test(registry): give the two income-chain oracles one revision to resolve against".

RECONSTRUCTED RECORD, written 2026-08-06 from the commit rather than contemporaneously.

What was shared and what was deliberately left duplicated is the substance. Only the revision resolution moved into `_ledger_income_chain_oracle_support.py`. Two oracles reading DIFFERENT registry revisions would each be internally consistent while describing different law, and the disagreement would be invisible because neither asserts anything about the other. The invoice rows and expected figures stay duplicated because they differ by design -- scaffolding that differs should look different, not be forced through a shared helper with a flag.

## Verification

```
uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests -n 0 -q
```

The shared module builds its revision through the real snapshot construction rather than a hand-assembled one, so the bindings the oracles resolve are the ones a production calculate would load. A hand-built revision could agree with the tests and disagree with the filing, which is the failure an oracle exists to rule out rather than reproduce.

## Notes

Reconstructed under the plan-closure rule after `vault plan status` reported this Step checked with no execution record. The commit was located by SCOPE FILE, never by step id: a bare `git log --grep=S##` returns commits from other campaigns, because step ids are per-plan and collide across plans. That search returned confident, plausible, entirely wrong matches for every one of the nine unrecorded steps before the namespace error was caught.
