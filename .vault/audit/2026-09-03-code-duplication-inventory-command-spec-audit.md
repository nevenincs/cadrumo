---
tags:
  - '#audit'
  - '#code-duplication'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:828ff83f7047efddb9f1fb966be53395d998e69c7376a5b3bf691c8ac339bdca'
related:
  - "[[2026-09-03-code-duplication-ledger-invoice-lifecycle-refactor-audit]]"
---
# `code-duplication` audit: `ledger inventory command-spec dedup review`

## Scope

Independent read-only review of `d4c500d9c4` across the inventory command declarations, their new canonical parameter owner, the focused inventory and established management command-spec tests, and the whole-tree clone scan. The review verified complete parameter equality and order, requiredness, defaults, declarations, help keys, transport fields, exact object identity, frozen-record custody, and the retained analysis-versus-lifecycle `taxable_base` distinction.

## Findings

No blocking findings were identified. The shared `actividad_id` records remain separate by parameter kind: the positional inventory argument cannot substitute for the named analysis option. The `year` option is wholly equal at all four consumers and shares one frozen object. Full independent expected-record equality protects every runtime parameter field and tuple order, while exact identity assertions protect the three canonical records. The retained scan group does not justify cross-domain sharing: its analysis `taxable_base` has the inventory-specific `cli.app.ledger.inventory.taxable_base_help` contract, while the ledger lifecycle update option carries `cli.ledger.update.taxable_base_help`; they are different declared operator contracts despite mechanically similar option fields.

## Recommendations

Approve the consolidation. Retain the lifecycle `taxable_base` group as advisory, out-of-scope clone evidence unless a future decision first unifies its operator-facing help and domain contract with inventory movement entry.
