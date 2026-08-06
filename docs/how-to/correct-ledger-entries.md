# Correct mistakes in your ledger

Fix wrong transactions in your ledger without losing track of what changed. Every correction leaves a visible history entry, so you can always see what a transaction looked like before and after. Everything happens on your computer - nothing is sent anywhere.

## Before you start

You need:

- An active taxpayer profile. Every command below works on the active profile; if none is set, the command refuses. See [Set up your taxpayer profile](profile-setup.md).
- A master-key passphrase. The tool prompts for it the first time it opens your encrypted storage in a session.
- A ledger with transactions in it.

To find the transaction you want to fix, list your transactions and view one in detail. The sequence below records an example expense, lists the ledger, and inspects that row:

```{cli-sequence} correct-find-transaction
:verify: Confirm the inspected transaction is the one you want to fix.
```

The `view` command reports the id, amount, direction, description, and lifecycle state. The [transactions guide](import-bank-statements.md) covers listing and filtering in depth.

## Pick your fix

- If one transaction has a wrong amount, date, or text, [update it](#update-fields-on-a-transaction).
- If a transaction should not exist at all, [remove it](#remove-a-transaction).
- If the same purchase was imported twice, remove the duplicate - or [archive it](#archive-a-transaction) to keep a deliberate trace of it.
- If one payment covers two different things, [split it](#split-one-transaction-into-parts).
- If you split something and want it back together, [merge the parts](#merge-split-parts-back).
- If you're unsure about a transaction and want it out of the way, [stash it](#stash-a-transaction-you-are-unsure-about).
- If you want to keep a transaction in history but out of everyday lists, [archive it](#archive-a-transaction).
- If you stashed or archived a transaction by mistake, [restore it to active](#restore-a-stashed-or-archived-transaction).

(update-fields-on-a-transaction)=
## Update fields on a transaction

Change one or more fields directly. The sequence records a chair at the wrong price, corrects the amount and description, and confirms the correction:

```{cli-sequence} correct-update-fields
:verify: Confirm the update replaced the amount and description.
```

Each flag fully replaces that field - write the complete new value, not an addition to the old one. Write the amount as a positive figure - the direction field carries whether money came in or went out, and a negative amount is refused. The updatable fields are: date, value-date, amount, direction, currency, counterparty, description, taxable-base, iva-rate, iva-amount, irpf-category, notes, and group.

An update gives the transaction a new ID - the update output prints it. You don't have to track the change for read commands: an ID you wrote down before the update still answers in `history`, `view`, and `track`, resolving to the corrected transaction, exactly as the `view` above does. For a further mutation - another `update`, `classify`, or `archive` - use the current ID from the update output or from `list`, because those commands act on the live transaction.

Update works on active transactions only. Archived and stashed transactions refuse it, as does a split parent - the active parts of a split can be updated normally.

(remove-a-transaction)=
## Remove a transaction

Remove deletes a transaction from your active records. Preview it first with `--dry-run`, then remove it for real. The removed id no longer resolves, which is how the sequence confirms the deletion:

```{cli-sequence} correct-remove-transaction
:verify: Confirm the removed transaction no longer resolves.
```

A removed transaction is gone from your active records: the final `view` refuses because the id no longer names an active row.

(split-one-transaction-into-parts)=
## Split one transaction into parts

When one payment covers two different things - for example, a card payment that mixes business and personal items - split it into parts. Amounts and descriptions pair up one per part: the first amount goes with the first description, and so on:

```{cli-sequence} correct-split-transaction
:verify: Confirm the split produced two active child parts.
```

The original transaction becomes the split parent, and the parts carry the balance from then on. The split output prints one `child_transactions` row per part, each with a short `display_id` and a full `full_id`. Copy those ids - the merge command needs them to undo the split.

(merge-split-parts-back)=
## Merge split parts back

To undo a split, merge the parts back together using the child ids the split printed. Name every sibling part - the command refuses a partial merge. The sequence splits a payment, then merges the parts into one fresh transaction:

```{cli-sequence} correct-merge-parts
:verify: Confirm the merge produced a single active transaction carrying the full amount.
```

The parts and the original parent move to history, and the merge creates a fresh transaction in their place. If you no longer have the split output, the parts are active rows: run `aeat app ledger list` and read their ids from the listing.

(stash-a-transaction-you-are-unsure-about)=
## Stash a transaction you are unsure about

Stash sets a transaction aside for later. A stashed transaction is kept out of ordinary work. The sequence stashes a row and confirms its new lifecycle state:

```{cli-sequence} correct-stash-transaction
:verify: Confirm the transaction moved to the stashed state.
```

Use stash for a row you have not resolved yet and archive for a row you have deliberately set aside, such as a confirmed duplicate. Both are reversible: [restore](#restore-a-stashed-or-archived-transaction) returns the row to active. The `stash` command prints the transaction's fields but not its new lifecycle state, so `view` is how you confirm the change took effect.

(archive-a-transaction)=
## Archive a transaction

Archive keeps a transaction in history but out of ordinary work - it's the right choice for duplicates you want to keep a deliberate trace of. The sequence archives a duplicate row and confirms the state change:

```{cli-sequence} correct-archive-transaction
:verify: Confirm the duplicate moved to the archived state.
```

Like stash, the command prints the transaction's fields but not its new lifecycle state, so `view` confirms the row now reads `ARCHIVED`.

(restore-a-stashed-or-archived-transaction)=
## Restore a stashed or archived transaction

If you stashed or archived a transaction by mistake, restore it to active. Restore is the inverse of stash and archive: the row returns to your everyday lists and totals. The sequence stashes a row and then restores it:

```{cli-sequence} correct-restore-transaction
:verify: Confirm the restored transaction is active again.
```

Restore accepts the same id prefix the other commands accept. To recover several rows stashed by mistake, restore each one by id - you do not need to reset the whole ledger. List does not have a stashed-only filter, so identify the stashed rows from the ids you stashed, or from each row's lifecycle state shown by `view`.

Restore refuses a row that is already active, and it refuses a row whose period you have already filed - restoring it would change the inputs behind a return you have presented. Restore one of these only after you have corrected the filing through an amendment.

## Review what changed

Every correction is recorded. To see every action on a transaction in order, run `ledger history`. The sequence splits a payment, then reads the history with the sibling flag to follow the whole split family:

```{cli-sequence} correct-review-history
:verify: Confirm the history records the transaction's events in order.
```

The history lists each action in order with its timestamp and event reference. Details such as the reason and the new values are in the JSON output. To see a value before a change, read the earlier events in the history. The [CLI reference](../cli/index.rst) covers every field the history shows.

## Evidence and corrections

An attached evidence record - a receipt or invoice - is not deleted when you correct a transaction. After a split or merge, check the new transactions and re-attach evidence where needed. The [evidence guide](ledger-evidence.md) covers attaching and checking evidence.

## Start over as a last resort

If the ledger is beyond repair - for example, after importing the wrong files repeatedly - clear it and rebuild. Preview first, then confirm. The sequence records a row, previews the reset, clears the ledger, and confirms nothing remains:

```{cli-sequence} correct-reset-ledger
:verify: Confirm the reset cleared the active ledger.
```

Reset clears the whole ledger for the active profile. Use the [transactions guide](import-bank-statements.md) to rebuild it from your statements.

## Where to get help

If a command refuses or fails, check the [troubleshooting guide](troubleshooting.md). Unfamiliar terms are explained in the {doc}`glossary </_generated/glossary>`. Before sharing command output with anyone, strip tax identifiers such as your NIF, CIF, DNI, NIE, or NII.

## Next steps

- [Import and manage transactions](import-bank-statements.md) - bring in new transactions.
- [Attach evidence to transactions](ledger-evidence.md) - back your corrections with receipts.
- [Classify transactions](classify-transactions.md) - prepare corrected rows for tax calculations.
- [CLI reference](../cli/index.rst) - full field detail for every ledger command.
