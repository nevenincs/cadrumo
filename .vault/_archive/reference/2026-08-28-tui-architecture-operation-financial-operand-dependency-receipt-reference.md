---
tags:
  - '#reference'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:d368fb120d1645bbc43921b1443a240169e0f1defd5717b2648fb2877e5eaf0b'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` reference: `operation financial operand dependency receipt`

The `TuiOperationFinancialOperandDependencyReceiptV1` for the transient financial
operand contract, produced and validated at the head recorded below. This receipt is
the prerequisite the Edit Contract C3 dependency receipt consumes.

## Ancestry and what this receipt attests to

This receipt makes a **path-scoped** ancestry claim, not a whole-tree one. It attests
that the nine paths enumerated under Source ancestry were clean at the recorded head at
mint time, and that the validator ran green against exactly those contents. It does not
claim the repository as a whole was clean; other work was in flight elsewhere and is
irrelevant to this evidence.

The distinction matters. An unscoped whole-tree ancestry claim decays the instant
anyone commits anything, and two such receipts for one subject can both read `PASSED`
while recording different heads, with no way to tell which is current. A path-scoped
claim stays true for as long as those paths are unchanged, and a later reader can
verify it in one command rather than trusting the assertion.

## Reproduction

Cleanliness was verified immediately before stamping, not asserted. Both commands below
are the exact ones run:

```
git status --porcelain -- <the nine paths under Source ancestry>
uv run --no-sync pytest src/cadrumo/application/operations/tests/test_financial_operand_dependency_receipt.py -m unit -n0 -q
```

The first returned empty. The second returned `10 passed`. Re-running them against the
recorded blob digests reproduces this receipt.

## Receipt

```json
{
  "receipt_schema": "TuiOperationFinancialOperandDependencyReceiptV1",
  "validator": "validate via test_financial_operand_dependency_receipt",
  "validator_module": "src/cadrumo/application/operations/tests/test_financial_operand_dependency_receipt.py",
  "validation_result": "PASSED",
  "receipt": {
    "schema_version": 1,
    "current_head_commit": "ff03ead7cd30df1d2bd2b48386e7ab39123b425c",
    "ancestry_scope": "path_scoped",
    "governing_adr": {
      "stem": "2026-08-11-tui-architecture-adr",
      "status": "accepted",
      "body_hash": "sha256:7a3c209e34e108fa9eced71ba5b11506adc0c597939aed8f29b8b43197422dea"
    },
    "protocol_surface": {
      "protocol": "OperationTransientFinancialOperandProtocolV1",
      "methods": ["declare_requirement", "expire_lapsed", "grant_access", "release"]
    },
    "schema_fingerprints": {
      "OperationTransientFinancialOperandDeclaration": "sha256:eac284fcd50e975d6e6a3f84e9ae167c8686d7ab6786b7d2c57b7f3b05b94cc8",
      "OperationTransientFinancialOperandRequirement": "sha256:950ab54b34ea0ae41fc0085b0e74486879bbf5ce88915ff363cc49340916f420",
      "OperationTransientFinancialOperandAcknowledgement": "sha256:e525e694a7813f842d8ab129303820d486ffd85d8b909e9da288e1391510821a",
      "OperationTransientFinancialOperandRefusal": "sha256:5a8ad5d26cb13699112b4454f9544bc80f565c6053f6a17e246da05a8527b313",
      "OperationTransientFinancialOperandExpiry": "sha256:e69760b64bfd5730431cb210b7fd67ddc6e1f0130d7a24a41e555c06c71dffd6",
      "OperationTransientFinancialOperandRelease": "sha256:03cd5e6e5c6581dbb1fd9c4cc68683dd260c6f5d33d4f3e24447b23070bf88e9",
      "OperationFinancialOperandCustodyCheckpoint": "sha256:3b4b6428206cba3071959339f9ad4b57dec85d0cd74c944b0dc77a0f1749d4a6"
    },
    "custody_states": [
      "awaiting_submission",
      "bound",
      "delivery_started",
      "delivery_acknowledged",
      "released",
      "expired",
      "cancelled"
    ],
    "crash_matrix": ["not_delivered", "delivery_uncertain", "delivered"],
    "non_retention_proof": "no record field and no protocol return type carries an amount; declaration bounds are the sole permitted Decimal",
    "production_definition_inventory": {
      "declaring_definitions": ["modelo.edit.apply"],
      "operand_kind": "modelo.edit.manual_casilla_override",
      "count": 1
    },
    "opens_edit_path": "modelo.edit.apply manual casilla override, bounded EUR scale 2, lifetime 5 minutes"
  }
}
```

## Source ancestry

Nine paths, each verified clean at the recorded head immediately before stamping. Blob
digests are the `git rev-parse HEAD:<path>` values, so a reader can confirm the exact
contents this receipt attests to.

| path | blob |
| --- | --- |
| `src/cadrumo/application/operations/financial_operand.py` | `27c3f6d3337c5c0d2017b1f276396ec3709f8378` |
| `src/cadrumo/application/operations/financial_operand_custody.py` | `f0cfdf3af5afc84d483f36ee73515df79be5a3be` |
| `src/cadrumo/application/operations/persistence/financial_operand_custody.py` | `9439794706c79cf8e3c9182a99247f404e7cfa76` |
| `src/cadrumo/adapters/persistence/operations/financial_operand_custody.py` | `8fc7c60d53082b5b029b4d4a92c5a0b37c19ec41` |
| `src/cadrumo/application/operations/registry.py` | `ac6f52903ae1ef53dd4a9a90a08d6987139c3c0e` |
| `src/cadrumo/application/operations/owner.py` | `404ae3a6b1c080d90847c30e31e3037f2094e872` |
| `src/cadrumo/application/operations/tests/test_financial_operand_dependency_receipt.py` | `0c9a3484bcd2587e64e846b0a2f5f2de36ee462e` |
| `src/cadrumo/application/operations/tests/test_financial_operand_registration.py` | `615cf7d40cf93d0e5baad0284d834bb3400e47d9` |
| `.vault/adr/2026-08-11-tui-architecture-adr.md` | `56b786dd27129fdd75789893358bd8b628bf61ef` |

One path is deliberately absent from that table. The production definition inventory is
read from the modelo operation definitions module, which carried unrelated in-flight
work at mint time and so could not be attested clean. The inventory above was therefore
read from that module's committed content at the recorded head, and the sole operand
declaration was confirmed byte-identical between that committed content and the working
copy before the figure was recorded. The inventory is a claim about the head, not about
the working tree.

## Mutation proofs

The validator's load-bearing assertions were proven capable of failing before this
receipt reported them. A receipt over an assertion that cannot fail is worse than no
receipt, because it lends an authoritative name to a check doing no work.

**Duplicate-authority census.** A second `OperationTransientFinancialOperandDeclaration`
class and a second `advance_custody` function were introduced inside the searched
package; the census red on its single-declaration assertion. This proof required a
transient file in the tree because the assertion is an AST walk over a real directory
and offers no injection seam; the file was created and removed inside one shell
invocation with a trap-based cleanup, and its absence confirmed afterwards.

**Non-retention, both directions independently.** Injecting a `Decimal` field named
`retained_amount` reds the forbidden-name check. Injecting the same `Decimal` under the
benign name `settlement_quantity` reds the annotation check separately. The second
proof is the one that matters: the name check fires first and would otherwise mask an
annotation check doing nothing. Both were driven from an out-of-repo pytest plugin,
mutating nothing in the tree.

## What this receipt does not claim

It does not claim the operand contract is reached by production. Nothing under
`entrypoints/` submits `modelo.edit.apply`; the operation is enrolled and its operand
declared, but no caller exists. Wiring that submission is a later concern and is
deliberately outside this receipt.

The declaration is therefore currently unexercised in production: the manual override
amount crosses fully typed and pre-admitted through the Edit Contract admission phase,
so nothing asks the operator for it mid-flight today. The broker side is nevertheless
reachable, because `OperationExecutorContext` exposes a `financial_operand` accessor.

A stale source comment asserted the opposite of that last fact, stating that no
accessor existed and therefore no executor could exercise the broker side. The accessor
had since landed. The comment was corrected while minting this receipt, because a
receipt attesting to a contract should not certify a tree whose own prose contradicts
it.
