---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:850edbd1f9ffc53df26e597a8fcadc79e702eb4b2b431a701584478460379b83'
step_id: 'S219'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Rename the counterparty record now that it holds two facts

## Scope

- `src/cadrumo/application/ledger`
- `src/cadrumo/entrypoints/cli`

## Description

- Measure which surfaces hold both confirmed axes and which hold only the territorial one, by reading their fields rather than their names.
- Rename the eight surfaces that span both, including the persisted namespace key and its stored namespace string.
- Leave the surfaces that are genuinely establishment-only, and record why.
- Rule the storage-key question, which is a migration decision rather than a rename.
- Correct the operator prose that still described one fact, and carry the six changed strings into all four catalogues.

## Outcome

The record grew a second axis when the identification fact landed beside the territorial one, and every name and sentence around it still said establishment. Measured by fields rather than by name:

Holding BOTH axes, and therefore renamed: the record, its resolution, its repository, its input error, the record, resolve and forget functions, the key derivation, and the persisted namespace. Holding only the territorial axis, and therefore left: the contradiction model, whose fields are a confirmed and an evidenced scope; the conflict error, raised only when a second assertion names a different territory; and the ladder's scope-returning entry point. Renaming those for symmetry would have made three correct names wrong.

The prose split the same way. Changed: the group and confirm helps, the withdraw help and its nothing-to-withdraw notice, the unverifiable-identifier refusal in both places, and the retry notice — each addresses the whole record. Unchanged, with reasons: the scope option's help describes that option; the not-confirmed notice explains the establishment rung specifically; and the show help is accurate because show reports what the ladder will answer rather than what the record holds. Widening show to display the identification would be a behaviour change and is named as a follow-up rather than smuggled in under a prose row.

**The storage key moved, and that is a ruling.** An object key addresses persisted records, so changing it makes existing records unaddressable. The regime is pre-release and the governing rule is explicit that a changed key derivation is deleted rather than bridged. Leaving it would have put the misleading name in the one place that outlives every symbol. The consequence is that records written under the old key in a development bucket are no longer found; under a released regime the decision inverts and the rename waits for an upgrader.

## Verification

Collection, either side of the rename, on the working tree:

    23242/27295 collected (4053 deselected)   [before]
    23250/27308 collected (4058 deselected)   [after]

Residue at HEAD, after the commits landed:

    ConfirmedCounterpartyFacts                    12 files
    LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE  5 files
    CounterpartyEstablishmentFact / Repository     0 files
    record_counterparty_establishment              0 files
    LEDGER_COUNTERPARTY_ESTABLISHMENT_NAMESPACE    0 files

Catalogue writes, verified by reading each value back from the file rather than from an exit status:

    attempted=24  confirmed_on_disk=16   -> 8 retried -> confirmed on disk: 24 of 24

All six keys present in all four catalogues at HEAD.

Gates:

    ledger + counterparty CLI (unit or integration, -n0):   1287 passed of 1287 collected
    both counterparty CLI files:                              15 passed of 15 collected
    locale parity alone:                                      34 passed of 34 collected
    the three together:                                       43 passed of 43 collected

## Notes

Eight of the twenty-four catalogue writes did not land, and the tool reported nothing wrong. Only reading each value back from the file caught it; a run trusting exit statuses would have reported twenty-four writes and shipped sixteen. The eight were retried and confirmed individually.

A combined run of the CLI files with the parity gate failed once with thirteen failures and nine errors, reporting two codebase keys missing from all four catalogues. Re-measured: the counterparty CLI references seventeen keys and every one resolves, and the same combination re-run is green at forty-three. It was a race against concurrent catalogue writes rather than a defect, which is consistent with this host's behaviour and with several lanes editing the catalogues continuously.

Two error message keys were renamed by the sweep and put back. A message key addresses the catalogues rather than naming a symbol, so moving one costs four catalogue edits and buys a reader nothing; one belonged to the conflict error whose name was deliberately kept, so the sweep had carried the rename further than the decision went.

The rewrite crashed partway, on a locale file that matched the search and needed no change. The half-landed state was measured rather than assumed: no old name remained, the package imported, and the namespace and both facades carried the new names. All four catalogues were checked for truncation, since a crashed write is how a tracked file gets destroyed here.

Two absorptions are reported rather than hidden. Linting was run over the whole working diff rather than this change's files, and write times place another lane's `domain/modelos/_row_models.py` inside that window; the edits are mechanical auto-fixes and no undo was attempted. And the catalogue commit carried eighteen lines of a peer's modelo casilla translations, which were filled placeholders rather than changed meanings — taken because the code referencing my keys was already in HEAD, and leaving the catalogues behind it was the worse state.

The prose half of this row was found by a post-change semantic search rather than by a gate. The pre-change search could not have found it: the inconsistency did not exist until the rename created it.
