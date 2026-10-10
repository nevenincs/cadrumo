---
tags:
  - '#reference'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-10'
body_schema: 'body-v2'
body_hash: 'sha256:1877874f260c75afa02a92fb7559dac29fe712e08a7d709393c4fd0ef4dd7e78'
related: []
---

# `mcp-parity` reference: `agent provenance`

This record collects the code facts that bear on how a ledger fact stated by an agent is told from one typed by the person, read by Cadrumo's own reader, or derived by the registry. Every locator is relative to the root of this repository, on branch `feature/tui`, read on 2026-10-10 by static analysis with nothing executed; the tree held other sessions' uncommitted work. It states facts only and recommends nothing.

## Summary

- Four ledger writes accept a taxable base, a rate and a tax amount from their caller, with a free-text actor that falls back to the profile id (section 1).
- A row already stores who created it, a source command, a lineage and a classifier attribution from a closed vocabulary. That vocabulary has no member for an agent caller, and an executor cannot see who called it (section 2).
- A registry derivation from category, date and gross exists and stamps its own attribution (section 3).
- Nothing in aggregation reads who entered a row, and a row reads as reviewed whenever it is classified (section 4).

## 1. What the four writes accept

- `ledger.add`, `ledger.update` and `ledger.classify.single` accept a taxable base, a rate and a tax amount from the caller; `ledger.add` also accepts a surcharge amount (`src/cadrumo/application/ledger/ledger_add_contracts.py:66-68`, `:74`; `update_contracts.py:84-86`; `classify_requests.py:77-79`).
- `ledger.classify.bulk` accepts CSV text (`src/cadrumo/application/ledger/bulk_classify_operation.py:70`).
- Each of the four takes an optional free-text `actor`, and the executor falls back to the profile id (`ledger_add_contracts.py:84`; `update_contracts.py:155`; `classify_requests.py:167`; `bulk_classify_operation.py:71`; `ledger_add_command.py:104`; `classify_operation.py:133`; `bulk_classify_operation.py:149`).
- The source command stamped on the row is a constant in the operation that names the command-line verb, whatever the frontend (`ledger_add_command.py:105`; `classify_operation.py:134`; `bulk_classify_operation.py:150`).
- All four definitions admit only the command line today (`add_operation.py:179`; `update_operation.py:344`; `classify_operation.py:169`; `bulk_classify_operation.py:237`).
- The command line's refusal of pipeline-owned classifications is repeated in the operations (`src/cadrumo/entrypoints/cli/_ledger.py:90-96`; `ledger_add_command.py:203-204`; `classify_requests.py:88-99`); the check at `_ledger.py:386-392` selects among command-line modes and guards no value the single-classify operation accepts; the M210 option agreement is in the request (`classify_requests.py:224-244`).

## 2. The provenance a row carries today

- A row stores who created it, the source command, an edit lineage, the classifier attribution and a classification history (`src/cadrumo/domain/transactions/models.py:549-553`, `:559-563`; `lineage_models.py:47-56`, `:196-205`, `:221-229`).
- The classifier attribution is a closed set of shapes: `auto`, `manual`, `rule:<id>`, `llm:<model>`, `derived:<basis>` (`src/cadrumo/domain/transactions/model_validation.py:71-81`; `src/cadrumo/core/external_constants.py:61-68`).
- A direct classification stamps `manual`; Cadrumo's classifier stamps its own provenance; the registry derivation stamps `derived:iva-category`; a rule stamps `rule:<id>` (`actions_manual.py:1696-1715`; `llm_classification.py:951`, `:1049`, `:1473`; `actions_classification.py:615`).
- A manually added row keeps the stated base, rate, tax amount, actor and source command verbatim in its raw fields, with source format `manual` (`actions_manual.py:1768-1788`; `src/cadrumo/domain/transactions/raw_transaction.py:32-49`).
- The per-field origin vocabulary has members for document readings, the operator and derived values, and none for an agent caller; the classifier-input vocabulary has document, profile and operator assertion (`src/cadrumo/core/field_origin.py:28-81`; `src/cadrumo/core/classifier_input_source.py:21-50`; `src/cadrumo/core/field_grounding.py:28-77`).
- The executor context exposes no session, frontend or caller kind (`src/cadrumo/application/operations/owner.py:209-265`).
- The admission provenance, captured inside the submit guard and kept encrypted, holds the frontend and the approved scope (`src/cadrumo/application/operations/provenance.py:16-34`; `src/cadrumo/application/user_profile/access_contracts.py:153-158`, `:352-368`; `src/cadrumo/entrypoints/runtime/operation_authority.py:224-243`).
- The MCP `respond` tool already takes its actor from the session, in a typed `kind:id` grammar (`src/cadrumo_harness/mcp/admitted_operations.py:238-244`; `src/cadrumo/application/operations/interactions.py:23-26`; `src/cadrumo/entrypoints/runtime/operation_host.py:296`).

## 3. What the registry derives

- A category and a date resolve to one rate or to "not derivable", and the gross is split into base and tax amount by the registry rounding (`src/cadrumo/domain/iva/saturation.py:160-242`, `:245-257`).
- `ledger.classify.iva-derive` runs that derivation on a business row from the row's gross, stores the result with `derived:` attribution, and stores nothing when the category is not derivable (`operator_iva_operation.py:108-118`; `llm_classification.py:1015-1053`).
- The domain enforces gross equals base plus tax plus surcharge when base and tax are both present, with documented relaxations for self-assessed categories, withholding and rent (`src/cadrumo/domain/transactions/models.py:980-1058`).
- An accepted rule says of a model "it must never emit a tax rate, base, or amount", and an accepted record says a printed figure that disagrees with the derived one raises an advisory and never overwrites it (`.vault/adr/2026-06-04-llm-ledger-classification-adr.md:136-141`; `.vault/adr/2026-06-10-llm-evidence-classification-adr.md:111-116`).

## 4. What reads the provenance

- IVA aggregation uses the stored tax amount as the cuota, and screens a zero rate with a non-zero cuota, a rate that is not in the table, and a zero-by-law category with a rate; no comparison of the tax amount with base times rate was found in the lines read (`src/cadrumo/application/aggregation/_iva_transaction.py:287-324`, `:327-346`, `:414-424`).
- No file under `src/cadrumo/application/aggregation` reads the classifier attribution, the creator or the source command, and under `src/cadrumo/application` only ledger modules do (search, tests excluded).
- A row's review status is `reviewed` whenever its classification is business, personal or mixed, whoever classified it (`src/cadrumo/application/ledger/review_projection.py:66-75`; `src/cadrumo/application/search/installed_workbench.py:127-134`).
- Nothing under `src/cadrumo/entrypoints/tui` references the classifier attribution, the creator or the source command; the command line shows the attribution in the row view, and the ledger export has creator columns (search, tests excluded; `src/cadrumo/entrypoints/cli/_ledger_read_cli.py:601`; `actions_export.py:73-74`, `:239-240`).

## Not verified

- How the `ledger.update` executor stamps lineage and attribution. Only its contract was read.
- Which columns the bulk CSV carries.
- Whether aggregation screens a stated rate that is in the table but is not the rate of the stated category.
- How verification reads ledger rows; only the search of section 4 covers it.
- The invoice domain models' provenance vocabulary. Only the transaction models and the three core vocabularies were read.
- Which fields the terminal interface's row detail shows.
- Any registry rule for how far a stated tax amount may differ from a derived one. None was found.
