---
name: retired-enum-members-need-consumer-reconciliation
---

# Retired enum members need consumer reconciliation

## Rule

Before deleting a retired enum member, reconcile every validation, schema, fixture, and test consumer into one accept-or-reject state and prove the owning collection gate is green.

## Why

The `2026-06-11-ledger-hardening-close-audit` found that `AggregationSourceKind.INVOICE` looked retired at the CLI layer but still powered a contradictory registry-validation surface: schema construction accepted it, validation routed it positively, and selector validation rejected it. Deleting that member before reconciling consumers would break registry fixtures and hide whether the intended final state is acceptance or rejection. The project needs one coherent state before enum deletion.

## How

- **Good:** before removing an enum member, search production and test consumers, migrate fixtures to the replacement member, update validators so all paths either accept or reject consistently, then run the owning collection and behavior gates.
- **Good:** if collection is red from peer work, leave the deletion step open and record the blocker in an audit or plan note.
- **Bad:** deleting the enum member because no production TOML uses its string while schema, validator, and tests still construct or branch on the member.