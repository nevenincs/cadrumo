# Retired enum members need consumer reconciliation

## Rule

Before deleting a retired enum member, reconcile every validation, schema,
fixture, and test consumer into one coherent accept-or-reject state, and prove
the owning collection gate is green.

## Why

A member can look retired at the CLI layer while still powering a contradictory
registry-validation surface — schema construction accepting it, validation
routing it positively, and selector validation rejecting it, all at once.
Deleting the member before reconciling consumers breaks registry fixtures and
hides whether the intended final state is acceptance or rejection. The project
needs one coherent state before the deletion.

## How

- **Good:** search production and test consumers, migrate fixtures to the
  replacement member, update validators so every path either accepts or rejects
  consistently, then run the owning collection and behaviour gates.
- **Good:** if collection is red from peer work, leave the deletion open and
  record the blocker in an audit or plan note
  (`full-tree-gate-must-distinguish-owner`).
- **Bad:** deleting the member because no production TOML uses its string, while
  schema, validator and tests still construct or branch on it.

Companion: `binding-source-kind-single-taxonomy`.
