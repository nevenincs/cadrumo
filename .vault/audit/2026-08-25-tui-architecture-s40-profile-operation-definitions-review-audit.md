---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:3549e5a8de7837218ce9bdae42b53b53ecba7cee86be662424d41016964484da'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: S40 profile-operation definitions review

## Scope

Independent review of `W03.P08.S40`: the canonical profile operation population, its real supervisor integration proofs, the user-profile authority delegation chain, the supporting owner-only executor contract, and the residual direct frontend-door inventory.

## Findings

### owner-contract-reexport-bridge | high | Resolved before S40 closure

`operations/owner.py` was a non-`__init__` forwarding module for the executor protocols while profile, auth, censal, and live owners imported it. That violated the canonical-home and no-re-export-bridge rules and contradicted the recorded S122 disposition. The relocation moved the executable protocol definitions into `operations/owner.py`, deleted `_executor.py`, swept every internal and test consumer, and added the live facade census assertion that the retired module does not exist. The S40 module retains its direct import from the now-canonical owner boundary; it contains no second executor protocol or profile operation definition population.

### direct-cli-profile-logout-door | medium | Owned downstream, not an S40 exception

The direct logout invocation in the CLI custody frontend remains an execution door. It is explicitly owned by `W06.P14.S157`, which replaces that call with the composed public operation API and deletes the application-authority path. The S40 completion record names that exact owner; no compatibility wrapper or duplicate logout executor is retained here.

## Recommendations

Complete `W06.P14.S157` before declaring the CLI/logout fixed point complete. Keep new profile-operation owners bound to `operations.owner` only for executor contracts, and keep frontend consumers on the public operation facade.
