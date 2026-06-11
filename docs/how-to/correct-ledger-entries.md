# Correct mistakes in your ledger

Fix wrong transactions in your ledger without losing track of what changed. Every correction leaves a visible history entry, so you can always see what a transaction looked like before and after. Everything happens on your computer - nothing is sent anywhere.

## Before you start

You need a ledger with transactions in it. To find the transaction you want to fix, list your transactions and view one in detail:

```bash
aeat app ledger list
aeat app ledger view <transaction-id>
```

The [transactions guide](import-bank-statements.md) covers listing and filtering in depth.

## Pick your fix

- If one transaction has a wrong amount, date, or text, [update it](#update-fields-on-a-transaction).
- If a transaction should not exist at all, [remove it](#remove-a-transaction).
- If the same purchase was imported twice, remove the duplicate - or [archive it](#archive-a-transaction) to keep a deliberate trace of it.
- If one payment covers two different things, [split it](#split-one-transaction-into-parts).
- If you split something and want it back together, [merge the parts](#merge-split-parts-back).
- If you're unsure about a transaction and want it out of the way, [stash it](#stash-a-transaction-you-are-unsure-about).
- If you want to keep a transaction in history but out of everyday lists, [archive it](#archive-a-transaction).
- If you stashed or archived a transaction by mistake, [restore it to active](#restore-a-stashed-or-archived-transaction).

## Update fields on a transaction

Change one or more fields directly:

```bash
aeat app ledger update --id <transaction-id> --amount=-121.00 --description "Office chair, corrected price"
```

Each flag fully replaces that field - write the complete new value, not an addition to the old one. The updatable fields are: date, value-date, amount, direction, currency, counterparty, description, taxable-base, iva-rate, iva-amount, irpf-category, notes, and group.

An update gives the transaction a new ID - the update output prints it. You don't have to track the change for read commands: an ID you wrote down before the update still answers in `history`, `view`, and `track`, resolving to the corrected transaction. For a further mutation - another `update`, `classify`, or `archive` - use the current ID from the update output or from `list`, because those commands act on the live transaction.

Update works on active transactions only. Archived and stashed transactions refuse it, as does a split parent - the active parts of a split can be updated normally.

## Remove a transaction

Remove deletes a transaction from your active records. To preview what would happen without deleting anything, run with `--dry-run` first:

```bash
aeat app ledger remove --id <transaction-id> --reason "wrong file imported" --dry-run
aeat app ledger remove --id <transaction-id> --reason "wrong file imported" --yes
```

## Split one transaction into parts

When one payment covers two different things - for example, a card payment that mixes business and personal items - split it into parts:

```bash
aeat app ledger split --id <transaction-id> --child-amount=-100.00 --child-description "office supplies" --child-amount=-21.00 --child-description "personal items" --reason "mixed receipt" --yes
```

Amounts and descriptions pair up one per part: the first amount goes with the first description, and so on. The original transaction becomes the split parent, and the parts carry the balance from then on.

## Merge split parts back

To undo a split, merge the parts back together. Name every sibling part - the command refuses a partial merge:

```bash
aeat app ledger merge --child-id <id1> --child-id <id2> --reason "undo split" --yes
```

The parts and the original parent move to history, and the merge creates a fresh transaction in their place.

## Stash a transaction you are unsure about

Stash sets a transaction aside. A stashed transaction leaves the everyday lists and totals.

Use stash for a row you have not resolved yet and archive for a row you have deliberately set aside, such as a confirmed duplicate. Both are reversible: [restore](#restore-a-stashed-or-archived-transaction) returns the row to active.

```bash
aeat app ledger stash --id <transaction-id> --reason "waiting for invoice" --yes
```

## Archive a transaction

Archive keeps a transaction in history but out of ordinary work - it's the right choice for duplicates you want to keep a deliberate trace of:

```bash
aeat app ledger archive --id <transaction-id> --reason "duplicate imported row" --yes
```

## Restore a stashed or archived transaction

If you stashed or archived a transaction by mistake, restore it to active. Restore is the inverse of stash and archive: the row returns to your everyday lists and totals.

```bash
aeat app ledger restore --id <transaction-id> --reason "stashed by mistake" --yes
```

Restore accepts the same id prefix the other commands accept. To recover several rows stashed by mistake, list the stashed rows first, then restore each one - you do not need to reset the whole ledger:

```bash
aeat app ledger list --filter classification=NOT_YET_PROCESSED
aeat app ledger restore --id <transaction-id> --reason "bulk stash undo" --yes
```

Restore refuses a row that is already active, and it refuses a row whose period you have already filed - restoring it would change the inputs behind a return you have presented. Restore one of these only after you have corrected the filing through an amendment.

## Review what changed

Every correction is recorded. To see every action on a transaction in order, run:

```bash
aeat app ledger history <transaction-id>
```

The history lists each action in order with its timestamp and event reference. Details such as the reason and the new values are in the JSON output. To see a value before a change, read the earlier events in the history. To follow a whole split family, add `--include-split-siblings`:

```bash
aeat app ledger history <transaction-id> --include-split-siblings
```

The [CLI reference](../cli/index.rst) covers every field the history shows.

## Evidence and corrections

An attached evidence record - a receipt or invoice - is not deleted when you correct a transaction. After a split or merge, check the new transactions and re-attach evidence where needed. The [evidence guide](ledger-evidence.md) covers attaching and checking evidence.

## Start over as a last resort

If the ledger is beyond repair - for example, after importing the wrong files repeatedly - clear it and rebuild. Preview first:

```bash
aeat app ledger reset --reason "re-importing all statements" --dry-run
aeat app ledger reset --reason "re-importing all statements" --yes
```

Reset clears the whole ledger for the active profile. Use the [transactions guide](import-bank-statements.md) to rebuild it from your statements.

## Where to get help

If a command refuses or fails, check the [troubleshooting guide](troubleshooting.md). Unfamiliar terms are explained in the {doc}`glossary </_generated/glossary>`. Before sharing command output with anyone, strip tax identifiers such as your NIF, CIF, DNI, NIE, or NII.

## Next steps

- [Work with transactions](import-bank-statements.md) - bring in new transactions.
- [Attach evidence to transactions](ledger-evidence.md) - back your corrections with receipts.
- [Classify transactions](classify-transactions.md) - prepare corrected rows for tax calculations.
- [CLI reference](../cli/index.rst) - full field detail for every ledger command.
