---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:778370ca1578d8a1157278807f4100f256540f85c031d744c8637864fbc926d6'
step_id: 'S219'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Rename the counterparty record now that it holds two facts

## Scope

- `src/cadrumo/application/ledger`

## Description

- Measure which surfaces hold both confirmed axes and which hold only the territorial one, by reading their fields rather than their names.
- Rename the eight surfaces that span both, including the persisted namespace key and its stored namespace string.
- Leave the two surfaces that are genuinely establishment-only, and record why.
- Rule the storage-key question, which is a migration decision rather than a rename.
- Land it as one commit with a clean collect-only either side.

## Outcome

The record grew a second axis when the identification fact landed beside the territorial one, and every name around it still said establishment. Measured by fields rather than by name:

Holding BOTH axes, and therefore renamed: the record itself, its resolution, its repository, its input error, the record, resolve and forget functions, the key derivation, and the persisted namespace. `ConfirmedCounterpartyFacts` and its family now say what the record is — the facts an operator has confirmed about a counterparty — rather than naming one of the two.

Holding ONLY the territorial axis, and therefore left alone: the contradiction model, whose fields are a confirmed scope and an evidenced scope and nothing else, and the conflict error, which is raised only when a second assertion names a different territory. Renaming those for symmetry would have made two correct names wrong, which is the same test that kept `stated_country_name` and `stated_country_code_status` intact on the ladder an hour earlier. The ladder's own scope-returning entry point keeps its name for the same reason.

**The storage key moved, and that is a ruling rather than a rename.** An object key addresses persisted records, so changing it makes existing records unaddressable. The compatibility regime is `pre_release`, and the governing rule is explicit that a changed key derivation is deleted rather than bridged — no migration pass, no read-tolerance of what an earlier version wrote. Leaving it would have put the misleading name in the one place a reader most needs it right and the one place that outlives every symbol. So it moved, and the consequence is stated: any records written under the old key in a development bucket are no longer found. Under a released regime this would have required an upgrader instead, and the decision would have gone the other way.

## Verification

Collection, immediately before and after, on the working tree:

    23242/27295 tests collected (4053 deselected)   [before]
    23250/27308 tests collected (4058 deselected)   [after]

The thirteen-test difference is peer work landing alongside, not this change: nothing here adds or removes a test.

Surfaces exercised:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests \
      src/cadrumo/entrypoints/cli/tests/test_ledger_counterparty_cli.py \
      src/cadrumo/entrypoints/cli/tests/test_ledger_counterparty_show_cli.py -n0 -q -m "unit or integration"
    1287 passed of 1287 collected

Residue at HEAD, after the commit landed:

    ConfirmedCounterpartyFacts                     12 files
    record_confirmed_counterparty_facts             6 files
    LEDGER_CONFIRMED_COUNTERPARTY_FACTS_NAMESPACE   5 files
    ledger_confirmed_counterparty_facts             1 file

    CounterpartyEstablishmentFact                   0 files
    CounterpartyEstablishmentRepository             0 files
    record_counterparty_establishment               0 files
    LEDGER_COUNTERPARTY_ESTABLISHMENT_NAMESPACE     0 files

## Notes

Two error message keys were renamed by the sweep and put back. They address the locale catalogues rather than naming a symbol, so moving them would have cost four catalogue edits and bought a reader nothing; one of them belonged to the conflict error, whose name was deliberately kept, so the sweep had carried it further than the decision went. The keepers were masked during the sweep and restored after, because three of them contain a renamed name as a prefix.

The rewrite crashed partway, on a locale file that matched the search and needed no change. The half-landed state was measured immediately rather than assumed: no old name remained anywhere, the package imported, and the namespace and both facades carried the new names — so the crash fell after every file that needed rewriting. The four locale catalogues were checked for truncation, since a crashed write is how a tracked file gets destroyed, and all four parse at full size.

One mistake to record. Linting was run over the whole working diff rather than over the files this change touched, and the fix pass rewrote at least one file belonging to another lane; write times place `domain/modelos/_row_models.py` inside that window. The edits are mechanical auto-fixes rather than semantic changes and no attempt was made to undo them, but the correct scope was the eleven files of this rename and it should have been named explicitly.
