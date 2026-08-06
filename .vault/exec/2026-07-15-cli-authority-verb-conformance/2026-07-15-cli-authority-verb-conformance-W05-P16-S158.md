---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:cebf43d4b583f2ead20c53af88ce50277c58d91b2f0f4ab0390dbcae90627629'
step_id: 'S158'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove canonical switch identity gating and removed sandbox-use unavailability

## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_identity_gate.py`

## Description

- Read the module for each half of the row separately rather than accepting a passing gate as covering both.
- Confirm the canonical switch half is genuinely proven, across the pure logic and the wired server.
- Find the sandbox-use half absent, with a positive control proving the search could have found it.
- Assert the retired keys are absent from the identity-changing set and from the exposed surface.
- Establish what the gate does with a retired key rather than only that it is gone.
- Assert the fail-closed answer, and prove it is the gate answering by showing a confirmed session admits the same call.

## Outcome

Half the row was proven and half was not. Both are now.

The canonical switch half was already strong and was left untouched. The module drives the pure decision logic and the real built server, proves an unconfirmed first mutation is refused, that an identity read clears it, that every member of the identity-changing set re-arms it, and that the refusal is byte-identical on the direct and `execute` paths.

Corrected claim: an earlier version of this record stated the gate proves "the absence of the removed sandbox-use door". It did not. The token `sandbox` appeared nowhere in the module before this change, established with a positive control on the same tool and path against a token the module does carry.

Two cases were added. The first asserts the canonical switch is in the identity-changing set, is exposed, and is allowed by the gate, and only then asserts the retired sandbox-use keys are in neither the set nor the exposed surface. The control runs first deliberately: every remaining claim is an absence, and an emptied set or a descriptor build returning nothing would satisfy them all while proving nothing.

The second case is the one worth keeping. Unavailability is a fact about today, so the gate's behaviour on a retired key is pinned as well: a key absent from the risk table classifies all-false, which means not read-only, so the gate treats a sandbox-use verb as an ordinary mutating call and refuses it on an unconfirmed session rather than waving it through by name as the retired design did. That property survives someone re-registering the verb without reading the gate module. The same case then shows a CONFIRMED session admits the identical call, which is what proves the refusal is the gate deciding rather than a dead key path refusing everything.

Measured on the CLI side rather than assumed: no sandbox-use key is registered, and the surviving sandbox family is eight `config.profile.sandbox` verbs with no `use` among them.

Each new assertion was mutation-proved by feeding it the canonical switch where a retired key is expected; both flipped to failure.

`uv run --no-sync pytest src/cadrumo/entrypoints/mcp -m "unit or integration"` reported `285 passed, 6 warnings in 83.02s`. `ruff check`, `ruff format --check` and `ty check` all reported clean.

## Notes

The gate's own docstring already said login is what enters a sandbox, by its canonical label. That sentence is why the source row was genuinely satisfied and is also why this test row looked satisfied: the reasoning was recorded at the site, so a reader checking the module found the right answer and could reasonably assume the tests carried it. They did not, and prose at the implementation is not a gate.

Not verified: whether any `config.profile.sandbox` verb changes which profile is active without passing through `config.login`. If one does, it would need to re-arm the gate and does not today. That was noticed while reading the identity-changing set and is outside this row, which is about the retired `use` door.
