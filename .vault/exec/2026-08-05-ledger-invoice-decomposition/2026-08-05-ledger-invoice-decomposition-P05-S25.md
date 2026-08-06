---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:66248c1fa9884025c33c19041079244c133d61336bebfe20b60262b3e9708c74'
step_id: 'S25'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---
# Gate every advisory message builder as constructible at zero, one and many items against its own model's declared cap, read from the field rather than restated

## Scope

- `src/cadrumo/tests`

## Description

- Add an AST scan enumerating every f-string/concatenation site that assembles a length-capped operator-prose field (`message`, `detail`, `details`, `note`, `summary`, `description`, `suggestion`) across production `cadrumo`.
- Measure each builder's static floor by summing its literal segments and counting every interpolated term as zero characters -- the "zero items" lower bound that holds for any data, including the many-item case.
- Read each field's cap from the live pydantic model (`model_fields[...].metadata[...].max_length`) rather than restating a copied number.
- Assert every builder's floor is at or below its cap (a breach is certain, not probabilistic: no input can rescue an unconstructible message).
- Add a shrink-only ratchet flagging a builder that leaves too little headroom for its interpolated terms (the "one or many items" variable-length exposure), seeded with the two pre-existing cramped `CalculationSourceDiagnostic` builders that already elide safely.

## Outcome

Landed as commit `21fb01aa79`, "tests(advisory): gate every advisory message as constructible against its own cap".

RECONSTRUCTED RECORD. Written on 2026-08-06 from the commit and its diff, not from a contemporaneous account. The Step was checked without a record and is being reconciled under the plan-closure rule; what follows is what the commit demonstrably does, with no verification claimed that cannot be re-run today.

The commit's own motivation is a prior incident: a campaign shipped an advisory with a static floor of 528 characters against a 512-character cap, unconstructible at any input, so a correctness decision was made on the promise of a message that could never fire. This gate targets exactly that shape (static over-cap), which is distinct from the variable-length shape (a message that grows with taxpayer data and crosses its cap at some item count) -- the module's own docstring names three of the latter that shipped in one day and were caught only at runtime.

## Verification

Verification is re-runnable rather than quoted from the original session:

```
uv run --no-sync pytest src/cadrumo/tests/test_advisory_message_constructibility.py -n 0 -q
```

## Notes

Reconstructed under the plan-closure rule after `vault plan status` reported this Step checked with no execution record. The commit was located by SCOPE FILE, never by step id: a bare `git log --grep=S##` returns commits from other campaigns, because step ids are per-plan and collide across plans. That search returned confident, plausible, entirely wrong matches before the namespace error was caught.
