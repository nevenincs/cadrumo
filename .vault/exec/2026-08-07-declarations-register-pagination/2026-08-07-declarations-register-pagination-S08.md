---
tags:
  - '#exec'
  - '#declarations-register-pagination'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:68dd3ed566e9a14fe6e2a28a9bf7ef9a8b5a72906e54539ead628defcf8eca89'
step_id: 'S08'
related:
  - "[[2026-08-07-declarations-register-pagination-plan]]"
---
## Description

The sweep's failure-absorption arm was untestable for one reason only: it took the
register, and a register cannot be opened offline. It never needed the register —
it used it for exactly one thing, building the walk coroutine. Narrowing the
parameter to that coroutine drops a dependency instead of adding one, and the arm
becomes drivable with a real coroutine.

## Outcome

- `_walk_or_failure_row` now takes `awaitable: Awaitable[tuple[Declaracion, ...]]`
  in place of `register: DeclaracionesRegisterSession`. Both call sites pass
  `register.walk(modelo=code, ejercicio=year)`, which is the same coroutine the
  helper used to build internally, so the behaviour is unchanged: it is awaited
  immediately, on the same line of control flow, with the same bound applied.
- The now-unused `DeclaracionesRegisterSession` import was dropped from the
  module.
- The parameter matches the sibling `_await_filed_register_walk`, which already
  takes `awaitable` and is already tested by being handed a real coroutine. This
  is that idiom applied one function further out, not a new one.

## Verification

A test drives the narrowed helper with two real coroutines: one raising the
genuine truncation refusal, one returning a real `Declaracion`. It asserts the
refusal is absorbed into a typed row and that the helper returns `None` so its
caller skips the pair, and that the healthy call returns its rows and adds no
row. Nothing is stubbed and no production path is patched. Module: 8 passed.
`ruff`, `ruff format --check` and `ty check` clean.

Mutation proof, via a pytest plugin outside the repository so no tracked file
changed: green, then the absorb clause narrowed from `except Exception` to
`except TimeoutError` — the plausible production defect that would let a refusal
escape — and the test reds with the refusal propagating uncaught, then green
again with the mutation removed.

## Notes

The boundary this covers, stated because it is the part a later reader will get
wrong: PER-PAIR failure absorption only. A real refusal becomes a row and the
pair is signalled for skipping. It does NOT cover CROSS-PAIR continuation — that
the sweep goes on to the next pair — which lives inside each bulk function behind
the live-session gate and is a separate row's job. Two different guarantees.

The first mutation attempted did not mutate anything and passed green, which
would have been a false proof had it been accepted. It patched
`_await_filed_register_walk` to await plainly, on the assumption the absorption
lived there; it does not, it lives one layer out in this helper's own except
clause, so the refusal still reached the absorber and the test still passed. A
mutation that does not flip the result has not proven the gate — it has only
proven the mutation missed. Worth recording because a green mutation run reads
exactly like a passing test.
