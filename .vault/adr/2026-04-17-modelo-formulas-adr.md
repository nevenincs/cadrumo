---
tags:
  - '#adr'
  - '#modelo-formulas'
date: '2026-04-17'
modified: '2026-07-17'
body_hash: 'sha256:6024af90e75c9e616856b3a3158e0e772162cf90c46082208dc8abb10ade4b21'
related:
  - '[[2026-04-17-modelo-formula-ruleset-research]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-20-registry-authority-flow-adr]]'
---

# Modelo formula engine authority | (**status:** `accepted`)

## Decision

All modelo formulas are typed registry data beneath
`src/cadrumo/_data/registry/aeat/modelos/`. The selected
`ModeloRevision` supplies formula nodes, operands, parameters, legal references,
and application bindings. `src/cadrumo/domain/calculations/registry/` validates
that graph and owns the sole formula runtime.

Application services resolve typed source evidence and invoke the selected
revision. CLI commands, filing builders, adapters, and individual modelo
modules do not redeclare equations or maintain parallel ruleset tables.

## Invariants

- Formula nodes use stable semantic casilla identifiers and typed decimal,
  enum, boolean, relation, or row operands.
- The graph is acyclic, all operands resolve, and every computed casilla has
  bundled legal grounding for the effective revision.
- Calculation is deterministic for the same revision and evidence bundle;
  ordering and rounding are explicit registry/runtime policy.
- Missing inputs, unknown nodes, cycles, revision mismatch, and ungrounded
  formulas are refusals, never zero/default substitution.
- Verification compares the resulting values with independent fixture or
  official-example oracles; tests do not reproduce formula logic.

## Consequences

Extending a modelo or filing year means extending and validating the central
registry. The retired `domain.casillas` formula stub, free-form expression
field, Python ruleset tree, duplicate engine, and compatibility imports are
absent.
