---
tags:
  - '#reference'
  - '#bank-agnostic-statement-import'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:fb301a0ca07a7f4366f80a2c497dcef58489dde307245322f699f64202a0d101'
related:
  - "[[2026-08-07-unstructured-document-ingestion-adr]]"
  - "[[2026-06-02-ledger-operator-hardening-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #reference) and one feature tag.
     Replace bank-agnostic-statement-import with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

# `bank-agnostic-statement-import` reference: `Bank-specific statement import code and the AI extraction seams it can move onto`

<!-- Brief description of what was researched and what sources were consulted.

Include any concrete references to files, line numbers, modules, etc. This is
the information that coding agents will consult during implementation. -->

## Summary

<!-- Findings pertinent to `bank-agnostic-statement-import` being considered. Include implementation
details and architecture overviews considered insightful, essential, or
relevant. Adapt format to content. -->

## Context

# `bank-agnostic-statement-import` reference: `Bank-specific statement import code and the AI extraction seams it can move onto`

Static code map taken on 2026-10-24 at `feature/tui` 043755a891, from four discovery passes (provider layer, operator interfaces, AI extraction, tests and docs) confirmed by direct reads.

## Bank-specific product code

- `src/cadrumo/adapters/inbound/financial/providers/pdf_n26.py`: the only PDF statement reader. It refuses any PDF without the `Kontoauszug` heading, an `N26 Bank AG` or `N26 Bank SE` marker and the German header `Beschreibung Verbuchungsdatum Betrag` (`pdf_n26.py:43-44`, `:246-254`). Rows come from one hand-written line regex that requires a sign and an `EUR` suffix (`:65-67`); counterparty dropping is keyed on German narratives (`:55-64`). Provider name `n26-pdf` prefixes synthetic transaction ids (`:115`, `:186-190`).
- `src/cadrumo/adapters/inbound/financial/providers/detection.py:41-55`, `:106-113`: the N26 provider sits in every candidate ordering and leads every PDF ordering. Without it a PDF has no reader at all.
- `src/cadrumo/application/ledger/actions_import.py:100`: operator token `pdf-n26`, mapped in `src/cadrumo/adapters/inbound/financial/ledger_import.py:91-92`, offered in `src/cadrumo/entrypoints/tui/ledger/import_flow.py:35`, `:48` and mirrored in the desktop frontend type union.
- `src/cadrumo/adapters/inbound/financial/providers/csv.py:162-182`: an `N26` CSV layout listed first in `CSV_LAYOUTS`. Its aliases are generic English and German header words (`date`, `amount`, `description`, `datum`, `betrag`), so every plain `Date,Description,Amount` export scores against it and receives `n26-` synthetic ids (`csv.py:317`, `:496-502`). The `N26 CSV` warning label special case lives at `csv.py:445-470`.
- The same file also carries BBVA, Santander, CaixaBank and Revolut layouts (`csv.py:112-161`), reused by the workbook providers through `workbook_layout.py:72`, `:122`.
- Product locale keys: `tui.ledger.import.provider.pdf_n26` and `adapters.inbound.financial.providers.pdf_n26.errors.parse_failed` in all four catalogues.

Stored provenance carries `provider_name` as free text (`src/cadrumo/domain/transactions/raw_transaction.py:78`); no record persists the operator token, so retiring it breaks no stored record.

## AI extraction seams already present

- Column-role mapping lane: `src/cadrumo/adapters/inbound/financial/providers/_mapped_tabular.py` reads tabular exports of no known layout through an application port (`src/cadrumo/application/ledger/column_roles.py`) bound by the composition root (`src/cadrumo/entrypoints/adapter_composition.py:1630-1633`, `:1719`) to the local-model mapper (`src/cadrumo/adapters/outbound/llm/column_role_mapping.py:674`). It reads delimited text only (`src/cadrumo/core/tabular.py:692-704`).
- The lane requires `INVOICE_DATE` and `GRAND_TOTAL` (`_mapped_tabular.py:64-69`) although `src/cadrumo/core/field_role.py:75`, `:84` define `BOOKED_DATE` and `MOVEMENT_AMOUNT` for statements and the mapper's prompt offers them, so a mapping that names the statement roles is refused.
- Invoice evidence reading: text layer or local vision transcription (`src/cadrumo/adapters/outbound/llm/evidence_draft_vision.py:147`), then a local text model, then deterministic anchoring (`src/cadrumo/application/ledger/invoice_draft_extraction.py:177`). Requests are marked evidence-derived so an off-host dispatch without consent refuses (`src/cadrumo/adapters/outbound/llm/client.py:467-468`).
- `src/cadrumo/application/ledger/document_transcription.py` is the in-memory transcription record with serialization tripwires; `src/cadrumo/application/ledger/evidence_textlayer.py:62` stamps a text-layer read.
- Local model catalogue defaults: `qwen3:1.7b` for text extraction and `qwen3-vl:2b` for vision (`src/cadrumo/core/model_catalogue.py:595-610`).

## Measured behaviour of the local text model

A prototype prompt run against `qwen3:1.7b` over the synthetic statement fixture `src/cadrumo/tests/fixtures/financial/n26/n26-savings-2025-01.pdf` returned every movement on the movement page correctly, and on the summary and note pages listed balances and totals as movements and invented two movements that the page does not print. Model output alone is therefore not filing grade; anchoring each movement to a printed line and reconciling printed balances is required.

## Tests, fixtures and documents naming the bank

- Product tests asserting bank-specific behaviour: `providers/tests/test_pdf_n26.py`, `test_detection_ordered.py`, `test_base.py:81`, `:175`, `test_source_byte_binding.py:117`, `test_csv.py:111-122`, `src/cadrumo/adapters/inbound/financial/tests/test_provider_id_dispatch.py:28`, `src/cadrumo/application/ledger/tests/test_provider_id_enum.py:63`, `src/cadrumo/entrypoints/cli/tests/test_ledger_corpus_import_export.py:114-116`, `dev/acceptance/ledger/tests/test_provenance_fixtures.py:18`, `:31`.
- Fixtures under `src/cadrumo/tests/fixtures/financial/n26/` and the corpus account `ledger-corpus/n26-savings.csv` are synthetic test data; the accepted ledger-operator-hardening decision names the latter as corpus data only.
- Documents presenting N26 as supported: `docs/how-to/import-bank-statements.md:34-35`, `:61`; `docs/reference/import-export-and-evidence.md:47`; `docs/technical/topics/document-and-financial-imports.md:32`; `docs/technical/articles/002-inbound-document-and-financial-adapters.md:24`; `docs/technical/articles/003-financial-providers-receipts-and-notification-pdfs.md:18`, `:34`, `:51`; their es, ca and hu catalogues; the captured help in `docs/_sequences/how-to/first-quarterly-filing/import-provider-list.json:17`.
- No accepted decision commits the product to an N26 reader.
