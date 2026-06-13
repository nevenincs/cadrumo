---
name: cli-single-subject-id-is-positional
---

# CLI single subject id is positional

## Rule

A CLI verb that addresses one ledger transaction must accept the id as a positional `Argument` resolved through the single shared transaction-id resolver, never as a `--id` option and never through a duplicated resolver.

## Why

The `2026-06-10-ledger-interface-contract-adr` recorded that ledger single-subject verbs had mixed `--id` options, positional arguments, optional ids, and duplicated `_resolve_id` helpers. That made documented-command conformance and operator muscle memory diverge. One positional subject id follows the CLI convention that the subject is an argument and flags configure the operation.

## How

- Good: `ledger view <transaction-id>`, `ledger history <transaction-id>`, and `ledger track <transaction-id>` all resolve through the same shared helper over `resolve_transaction_id`.
- Good: optional single-subject verbs still use an optional positional when the command semantics genuinely allow no subject.
- Bad: `ledger view --id tx_123` for a one-subject read or mutation verb.
- Bad: adding a second `_resolve_id` shim in a command module.
