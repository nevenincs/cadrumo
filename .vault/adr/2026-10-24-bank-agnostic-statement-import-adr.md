---
tags:
  - '#adr'
  - '#bank-agnostic-statement-import'
date: '2026-10-24'
modified: '2026-10-29'
body_schema: 'body-v2'
body_hash: 'sha256:45a699292d12f3f17f8aebe36522d8a9f0261c8fbcd2228f1bfe18eb12cbf5f0'
related:
  - "[[2026-10-24-bank-agnostic-statement-import-reference]]"
  - "[[2026-08-07-unstructured-document-ingestion-adr]]"
  - "[[2026-06-02-ledger-operator-hardening-adr]]"
---
# `bank-agnostic-statement-import` adr: `Bank-agnostic statement import: no bank-specific product code, PDF statements read by the local model and anchored deterministically` | (**status:** `accepted`)

## Problem Statement

Bank-statement import was pegged to named banks. The only PDF reader accepted German N26 monthly statements and nothing else, the operator chose it with the token `pdf-n26`, the generic English and German CSV header vocabulary was labelled as an N26 layout, and the CSV and spreadsheet readers carried private layouts for BBVA, Santander, CaixaBank and Revolut. Spain has many banks and their export formats change; supporting each one in product code is out of scope. The evidence is the `2026-10-24-bank-agnostic-statement-import-reference` code map.

## Considerations

- The operator ruled on 2026-10-24: remove every N26 mention and every code path hard-coded to that bank from the product; N26 statements stay acceptable as test data; extraction is an AI-backed process that must work for any PDF input, using the local models and extraction schemas.
- The operator ruled again the same day that the BBVA, Santander, CaixaBank and Revolut layouts may remain only as test examples: per-bank layouts are too broad an input to support, so only general tooling belongs in the product.
- The local text model reads real movement lines correctly but, on summary pages, lists balances and totals as movements and invents movements the page does not print (measured in the reference). Model output is a proposal, as the proposed unstructured-document-ingestion decision already holds in its anchoring and closure rule.
- A taxpayer statement is sensitive financial data; the import operation offers no off-host consent step.

## Considered options

- Keep per-bank PDF parsers and add more banks. Rejected by the operator's scope ruling.
- Extract PDF tables deterministically and feed the column-role mapping lane. Rejected for now: the text-line statements the product already meets carry no ruled tables, so table extraction yields nothing for them.
- Read each page with the local model into printed-form movement proposals, then anchor and reconcile them deterministically. Chosen.
- Keep per-bank CSV layouts beside a generic one. Rejected by the operator's second ruling; one vocabulary with conventions inferred from each file covers the same exports without naming a bank.

## Constraints

- Inbound adapters do not import outbound adapters; the reader is an application port bound by the composition root, like the column-role mapper.
- Reads stay on-host: every request is marked evidence-derived, so a misconfigured off-host provider refuses at the client's consent gate.
- CSV, OFX and spreadsheets whose headers the vocabulary names import with no model; only a PDF statement, or an export outside the vocabulary, needs the model lane, which runs through the agent service and refuses with its typed model or runtime reason when no model is available.

## Implementation

### D1 - One bank-agnostic PDF statement provider

`PdfStatementProvider` replaces the N26 reader. Each page is transcribed from its text layer, or by the on-host vision model when it has none, and the local text model proposes the page's movements as printed strings. A scanned page the vision model returns empty is read again, up to three attempts, and the model client never caches a blank completion, so one failed read is not replayed. The operator token becomes `pdf`; `pdf-n26` is retired with no alias. Detection offers the provider for PDF content after every exact fixed-layout provider.

### D2 - Deterministic anchoring decides what is a movement

A proposal survives only when its printed booked date and an amount the line prints appear together on one line of the page, and each line backs at most one movement. The amount is matched to the line by its digits, so a proposal that reformatted it still anchors, and the line's printed form is what gets parsed. A printed sign decides direction, and a model direction disagreeing with it is reported and ignored. For an amount printed without a sign, as in separate debit and credit columns, the running balances printed on the lines decide: the balance before plus or minus the amount must give the line's balance. Only when no balance proves it does the model's direction apply, and only for a movement an agreeing printed balance check spans; a direction resting on the model alone refuses the statement. A dated line that prints only a balance among lines that print running balances is a balance line, kept as the opening or closing balance rather than as a movement. Dates and amounts are parsed by the shared provider parsers under a statement-wide day-order and decimal-separator inference, month-name dates included in Spanish, Catalan, English and German; an amount whose separator stays ambiguous is dropped. A description or counterparty carrying words the page does not print is replaced by the anchored line's own text or dropped. Every dropped proposal is reported.

### D3 - Printed balances must reconcile, and every printed movement line must be accounted for

The model is asked for the page's opening and closing balances before its movements, and a balance it names only by its label is read from the one amount printed on the one line carrying that label. Every printed balance, whether opening, running or closing, is checked against the balance printed before it across every movement between them, in whichever order the statement lists them, so a movement line printing no balance is checked inside the span around it. A contradiction refuses the whole statement. A line printing a complete date and a non-zero amount that no accepted movement or printed balance accounts for may be a movement the model missed: it refuses the statement unless the balance checks chain from the printed opening balance to the printed closing balance, which proves nothing is missing, and then it is reported. A percentage is not an amount. A statement with no printed balance imports with a review warning only when every printed movement line is accounted for and every direction is printed.

### D4 - One bank-neutral tabular vocabulary, conventions inferred per file

The CSV and spreadsheet readers share one header vocabulary of ordinary Spanish, Catalan, English and German statement column names, most specific alias first; no bank-named layout remains, and the former bank exports are test data. Each file's date order and decimal separator are inferred from its own printed values by the same shared helpers the PDF grounding uses: dates printed in both orders refuse the file, and an amount whose separator stays ambiguous is refused rather than guessed. An export whose headers fall outside the vocabulary goes to the column-role mapping lane. Warnings name the format, and synthetic transaction ids carry the provider's name.

### D5 - The tabular mapping lane accepts the statement roles

The column-role lane accepts `booked_date` and `movement_amount` for a bank movement, falling back to the invoice date and total roles only when a mapping names those instead.

## Rationale

Anchoring every value to a printed line and reconciling printed balances is the anti-fabrication contract the product already applies to invoices. It lets a small local model serve any layout and language without a bank list, while a hallucinated or misplaced row cannot reach the ledger unreported. Inferring conventions from the file instead of from a bank's name keeps the deterministic readers general without weakening their refusals.

## Consequences

- PDF statement import needs a model chosen through the agent service; without one it refuses with the typed model or runtime reason.
- Statements whose dates print without a year, or whose movements wrap date and amount onto different lines, are refused row by row until a later decision widens anchoring.
- Synthetic transaction ids for CSV and spreadsheet rows without an id column change prefix for new imports.
- A CSV or spreadsheet whose header names fall outside the vocabulary needs the model-backed mapping lane.
- The on-host 2B vision model was measured on 2026-10-24 ignoring the reasoning switch and intermittently spending its whole output budget without returning text. Retries reduce this but do not remove it; a scanned page still unread refuses the statement rather than importing it short.
- The desktop frontend type union must follow the token change.
- Measured on 2026-10-24 with the on-host `qwen3:1.7b`: 106 text-layer statements, the ledger corpus rendered month by month in five layouts plus the three N26 fixtures. 101 imported exactly the expected movements, and 4 were refused by the balance or coverage checks for a model error: a lone movement missed on a second page, a mis-copied amount, and a running balance given as the closing balance. One could not be read because the host had no free memory for the model. None imported a wrong or missing movement.
- Reading a bank CSV export with a trailing summary row, or with a currency code in the amount header, is general tabular tooling under D4: the summary row is not a movement, and a total it prints must equal the sum of the movements or the export is refused.
- Approval basis: the operator's instructions of 2026-10-24 in the tui session, which directed this change, its AI-backed approach, and the removal of every bank-named CSV layout.
