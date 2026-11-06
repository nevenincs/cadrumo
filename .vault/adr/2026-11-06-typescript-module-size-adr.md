---
tags:
  - '#adr'
  - '#typescript-module-size'
date: '2026-11-06'
modified: '2026-11-06'
body_schema: 'body-v2'
body_hash: 'sha256:b61f09a8b0ed02c70b547d0e5e771706c06df922d2e083a51a3617b359e953fd'
related:
  - "[[2026-07-09-size-budget-refactor-adr]]"
  - "[[2026-11-06-typescript-module-size-reference]]"
---

# `typescript-module-size` adr: `TypeScript module and callable size bounds` | (**status:** `proposed`)

## Problem Statement

The operator ruled that the desktop application cannot be one monolithic file, and bounded every TypeScript module in the repository at 1500 physical lines. `dev/quality/typescript_module_size.py` enforces that bound absolutely, with no allowance list or baseline, and the ESLint `max-lines` rule gives editing feedback against the same constant. Review found that nothing bounds or declares the size of a single function, component or hook. The measurements in `2026-11-06-typescript-module-size-reference` show components and fixture factories of 900 to 1300 lines inside modules that pass. Two things need to be settled: whether a callable bound should exist, and how either bound relates to the accepted 2026-09-07 amendment of `2026-07-09-size-budget-refactor-adr`, which retired line-count ceilings for Python.

## Considerations

- The 2026-09-07 amendment rejects per-path and per-callable ceilings, baselines, slack bands and accept-growth regeneration, because they encode a temporary state and cannot judge responsibility.
- The TypeScript module bound has none of those mechanisms. It is one repository-wide constant with no exemption, and the operator demanded it explicitly.
- Product components and hooks hold almost all of the large callables. Plain functions are small: p99 is 130 lines (`2026-11-06-typescript-module-size-reference`).
- A large component is typically one closure that holds all of a page's state and handlers. Splitting it changes hook order and state lifetimes, so the split must be reviewed for behaviour, not just for size.

## Considered options

- **Absolute callable bound now, for example 300 lines, with no exemption.** This would fail about 90 top-level callables immediately, 40 of them over 500 lines, and block every other landing until a behaviour-sensitive refactor campaign finishes. It would also need an amendment to the 2026-09-07 ruling. Rejected as a gate today.
- **A ratcheted callable bound with per-callable overrides.** This is the exact mechanism the 2026-09-07 amendment retired. Rejected.
- **Keep the module bound as an operator-ruled absolute invariant, declare that no callable bound exists, and plan the refactors of the largest components, hooks and fixture factories by responsibility.** Chosen, pending acceptance.

## Constraints

- The module bound stays absolute: there is one definition (`MAX_PHYSICAL_LINES`), generators refuse to write past it, and there is no allowance list, baseline or exemption. A line ends at LF, CR or CRLF only.
- This ADR introduces no callable line ceiling, override table or baseline. Adding one later needs its own accepted decision that amends the 2026-09-07 ruling.
- Callable refactors preserve behaviour: hook order, state lifetimes and IPC calls are unchanged, and every consumer imports from the defining module.

## Implementation

We will record the 1500-line TypeScript module bound as a scoped, operator-ruled invariant. It is distinct from the retired Python ratchets because it is one absolute constant with no baseline. The gate and the ESLint comment will continue to state that callables are unbounded. Splitting the largest product components and hooks, and the fixture factories listed in the reference, belongs in a plan, sequenced by owner so the work does not collide with in-flight feature branches. Whether a component-size check is added after that campaign is a hypothesis for a later decision. It is not a commitment.

## Rationale

The module bound meets the operator's ruling without reintroducing the ratchet machinery the 2026-09-07 amendment retired, because it has no per-path state at all. A callable bound has no grounding yet: in this tree it would either fail at once on behaviour-sensitive code or need overrides, which the amendment forbids. Planning the refactors by responsibility addresses the measured concentration directly.

## Consequences

- Modules stay bounded and enforced by the gate, while single callables of up to about 1300 lines remain legal until the planned refactors land.
- Reconsider if the operator asks for a callable bound, or if callables grow after the refactor campaign. Either case needs a new decision that amends the 2026-09-07 ruling.
