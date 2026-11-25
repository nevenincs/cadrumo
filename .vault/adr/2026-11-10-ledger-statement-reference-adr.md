---
tags:
  - '#adr'
  - '#ledger-statement-reference'
date: '2026-11-10'
modified: '2026-11-10'
body_schema: 'body-v2'
body_hash: 'sha256:8e8a3e0ef2c756f465978a1c15010cc1d4dd108fe127b1ea5210008c7cea075f'
related:
  - "[[2026-10-24-bank-agnostic-statement-import-adr]]"
  - '[[2026-11-10-ledger-statement-reference-reference]]'
---

# `ledger-statement-reference` adr: `Serve the bank statement reference of a movement` | (**status:** `accepted`)

## Problem Statement

The ledger list and view never show the reference a bank statement printed for a movement, so a person or a persona journey can only match a ledger row to its statement line by date, amount, direction and description. The CSV reader already reads the statement's reference column (`src/cadrumo/adapters/inbound/financial/providers/csv.py:157`) but only as the row's provider identifier, which is replaced by a synthesized identifier when the statement prints none (`src/cadrumo/adapters/inbound/financial/providers/base.py:803`) and by `manual:`, `split:` or `merged:` identifiers after an edit, a split or a merge. No served field says which of these a row holds.

## Considerations

- The provider identifier is the bank's own id only when the statement printed one; otherwise it is an internal handle (`src/cadrumo/application/ledger/actions_manual.py:671`, `src/cadrumo/application/ledger/actions_split_merge.py:756`).
- An update rebuilds the raw record with manual provenance (`src/cadrumo/application/ledger/actions_manual.py:467`), so provenance cannot later prove what the statement printed.
- The content-addressed transaction id hashes an explicit payload (`src/cadrumo/domain/transactions/models.py:93`), so a new raw fact does not change any id or import deduplication.
- The transaction catalogue tolerates an absent optional field at the current envelope version (`src/cadrumo/adapters/persistence/profile/transactions.py:334`).
- Frontends render served words and facts only.

## Considered options

- A typed optional `statement_reference` on the raw transaction, set by the statement readers at the parse boundary and carried through edits, splits and merges. Kept: exact, survives every edit path, and costs one optional persisted fact.
- Derive the reference on read from the provider identifier and provenance. Rejected: an edited imported row has manual provenance, so a synthesized identifier can no longer be told from a printed reference without guessing at its spelling.
- Show the provider identifier as is. Rejected: it would present internal handles as a bank reference.

## Constraints

- The field holds only what the statement printed, trimmed and non-blank; a synthesized, manual, split or merged identifier never fills it.
- Rows stored before this field read as having no recorded reference; nothing is backfilled or inferred.
- The field is not part of the transaction id, the duplicate check or any tax calculation.
- The list, the view and the desktop render the served field and served words; no frontend derives it.
- The reference is private banking data. It lives only inside the encrypted transaction payload: never in the plaintext date-routing index (`src/cadrumo/adapters/persistence/profile/transaction_date_index_storage.py:117`, which carries ids and dates only) or any other plaintext index, a log line, an exception or CLI argv. `statement_reference` is an always-redacted key term in `src/cadrumo/core/redaction/rules.py`, so the log scrubber, error contexts, failure records and profile overview masking all redact it.
- The field is revision-relevant. The row revision hashes the stored payload bytes, so a change to the reference is a change to the row; updates, split parts and merged rows carry it. Serialization omits the field when it is `None`, so a row stored before it keeps identical bytes and an identical revision, and an old-shape row loads, edits and saves through the revision guard without a conflict.
- No envelope version bump: it is an optional field at the same envelope version. A bump would make every stored row unreadable, because schema lineage refuses a lower version and the only way through is an explicit atomic migration cutover.
- Downgrade: an older build, whose strict row model forbids extra keys, reads a row carrying the field as an unreadable or integrity-refused row and must not crash on it. Rows without a printed reference stay readable by an older build because the key is absent.

## Implementation

We will add `statement_reference: str | None` to the raw transaction record, set by the CSV, mapped tabular and OFX readers from the reference the statement printed and left empty by the PDF reader and by manual entries. Updates keep the current row's reference, and split parts and a merged row keep their parent's, because they remain the same bank movement. The canonical ledger payload serves it to `ledger.list`, `ledger view` and the desktop Ledger, with its label and the not-recorded words from the locale catalogue.

Proof runs through the real components: the CSV and OFX readers, the import, update, split and merge actions and the encrypted transaction catalogue repository (`src/cadrumo/adapters/persistence/profile/tests/test_statement_reference.py`), covering old- and new-shape round trips, an old-shape edit through the revision guard, and two rows differing only in the reference sharing one transaction id and deduplicating. The operation contract manifest is regenerated and the label words exist in en, es, ca and hu.

## Approval

Accepted 2026-11-11 by the coordinator under the operator's standing delegation of design decisions, with the conditions on custody and redaction, revision behaviour, the unchanged envelope version, identity independence, the regenerated manifest and four-language words folded into the constraints above.

## Rationale

Only the parse boundary knows whether the statement printed a reference, and every later edit path discards the provenance that could prove it, so recording it there as a typed fact is the one exact option.

## Consequences

Persona journeys and people can match ledger rows to statement lines by reference. Previously imported rows show no reference until they are imported again. Removing the field later would need a stored-row migration, because the catalogue rows are strict.
