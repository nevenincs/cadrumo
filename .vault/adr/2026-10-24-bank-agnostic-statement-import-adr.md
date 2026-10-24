---
tags:
  - '#adr'
  - '#bank-agnostic-statement-import'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:405192ac4816d58e53bf87f59383145753f91e5c3a357f76f70d90c6f9651924'
related:
  - "[[2026-10-24-bank-agnostic-statement-import-reference]]"
  - "[[2026-08-07-unstructured-document-ingestion-adr]]"
  - "[[2026-06-02-ledger-operator-hardening-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace bank-agnostic-statement-import with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, superseded, or deprecated. A new ADR starts as proposed; it
     moves to accepted or rejected when the decision is made; it becomes
     superseded when a later ADR replaces it (set by vault adr supersede,
     which also records superseded_by); and deprecated when it is retired
     without a direct successor.

     Reuse, amendment, and supersession follow the vaultspec system section.
     Preserve accepted content while a revision is pending; apply only an
     authorized amendment. Accept a reversal's successor before superseding
     its predecessor. Unchanged coverage needs no new record.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

# `bank-agnostic-statement-import` adr: `Bank-agnostic statement import: no bank-specific product code, PDF statements read by the local model and anchored deterministically` | (**status:** `{proposed|accepted|rejected|superseded|deprecated}`)

<!-- DOCUMENT BOUNDARY:
     Keep the ruling understandable on its own: scope, commitment, rationale,
     consequences. Cite detailed research/reference/audit evidence by stem.
     Each section may be a sentence; do not pad it to resemble a specification.
     Inconclusive experiments remain evidence, not an accepted decision. -->

## Problem Statement

<!-- The problem and why a decision is needed now, in this record's own
     terms. Do not re-narrate the research's evidence; cite it. -->

## Considerations

<!-- Only the forces that bear on the choice, each a terse line citing its
     grounding by stem or locator. Nothing the research already
     establishes is re-argued here. -->

## Considered options

<!-- Name each alternative evaluated, compared at the same level of abstraction, with its
key pros and cons and why it was kept or rejected. Naming the rejected options - not only
the chosen one - is what lets a future reader reconstruct the decision. Keep each option
to a terse claim-first line or two; the chosen option's full reasoning belongs under
Rationale. -->

## Constraints

<!-- Binding commitments and scope, including exceptions and affected prior rulings.
     Make obligations distinguishable from implementation hypotheses. -->

## Implementation

<!-- Lead with the chosen decision: "We will ..." and its scope. Follow with only the
     implementation outline needed to understand it. Mark hypotheses that may change
     within the constraints; keep task sequencing and code elsewhere. -->

## Rationale

<!-- Why this option wins against the drivers: a knockout criterion or a
     clear edge over the alternatives. Cite `{research}` findings and
     grounding `{reference}` by stem; do not restate them. A new fact
     surfacing here first belongs in the grounding document. -->

## Consequences

<!-- Benefits, accepted costs, and conditions that would require reconsideration.
     Acceptance does not assert that implementation is already complete. -->

## Context

# `bank-agnostic-statement-import` adr: `Bank-agnostic statement import: no bank-specific product code, PDF statements read by the local model and anchored deterministically` | (**status:** `accepted`)

## Problem Statement

Bank-statement import was pegged to one bank. The only PDF reader accepted German N26 monthly statements and nothing else, the operator chose it with the token `pdf-n26`, and the generic English and German CSV header vocabulary was labelled as an N26 layout. Spain has many banks and their export formats change; supporting each one in product code is out of scope. The evidence is the `2026-10-24-bank-agnostic-statement-import-reference` code map.

## Considerations

- The operator ruled on 2026-10-24: remove every N26 mention and every code path hard-coded to that bank from the product; N26 statements stay acceptable as test data; extraction is an AI-backed process that must work for any PDF input, using the local models and extraction schemas.
- The local text model reads real movement lines correctly but, on summary pages, lists balances and totals as movements and invents movements the page does not print (measured in the reference). Model output is a proposal, as the proposed unstructured-document-ingestion decision already holds in its anchoring and closure rule.
- A taxpayer statement is sensitive financial data; the import operation offers no off-host consent step.

## Considered options

- Keep per-bank PDF parsers and add more banks. Rejected by the operator's scope ruling.
- Extract PDF tables deterministically and feed the column-role mapping lane. Rejected for now: the text-line statements the product already meets carry no ruled tables, so table extraction yields nothing for them.
- Read each page with the local model into printed-form movement proposals, then anchor and reconcile them deterministically. Chosen.

## Constraints

- Inbound adapters do not import outbound adapters; the reader is an application port bound by the composition root, like the column-role mapper.
- Reads stay on-host: every request is marked evidence-derived, so a misconfigured off-host provider refuses at the client's consent gate.
- A host without the `llm` extra keeps importing CSV, OFX and spreadsheets; only a PDF statement meets the typed missing-extra refusal.

## Implementation

### D1 - One bank-agnostic PDF statement provider

`PdfStatementProvider` replaces the N26 reader. Each page is transcribed from its text layer, or by the on-host vision model when it has none, and the local text model proposes the page's movements as printed strings. The operator token becomes `pdf`; `pdf-n26` is retired with no alias. Detection offers the provider for PDF content after every exact fixed-layout provider.

### D2 - Deterministic anchoring decides what is a movement

A proposal survives only when its printed booked date and printed amount appear together on one line of the page, and each line backs at most one movement. A printed sign decides direction; the model's direction applies only to an unsigned amount, and a contradiction drops the row. Dates and amounts are parsed by the shared provider parsers under a statement-wide day-order and decimal-separator inference; an amount whose separator stays ambiguous is dropped. A description or counterparty carrying words the page does not print is replaced by the anchored line's own text or dropped. Every dropped proposal is reported.

### D3 - Printed balances must reconcile

Where the page prints an opening and closing balance, or running balances on movement lines, the anchored movements must sum to them exactly. A contradiction refuses the whole statement. A statement with no printed balance imports with a warning that no reconciliation was possible, so the operator reviews the preview.

### D4 - Generic CSV vocabulary carries no bank name

The former N26 CSV layout becomes the generic layout with the same aliases. Its warnings read `CSV` and its synthetic transaction ids carry a neutral prefix. Removing the remaining bank-named CSV layouts is a separate decision this record does not take.

### D5 - The tabular mapping lane accepts the statement roles

The column-role lane accepts `booked_date` and `movement_amount` for a bank movement, falling back to the invoice date and total roles only when a mapping names those instead.

## Rationale

Anchoring every value to a printed line and reconciling printed balances is the anti-fabrication contract the product already applies to invoices. It lets a small local model serve any layout and language without a bank list, while a hallucinated or misplaced row cannot reach the ledger unreported.

## Consequences

- PDF statement import needs the `llm` extra and a local model runtime; without them it refuses with the typed missing-extra facts.
- Statements whose dates print without a year, or whose movements wrap date and amount onto different lines, are refused row by row until a later decision widens anchoring.
- Synthetic transaction ids for generic CSV rows without an id column change prefix for new imports.
- The desktop frontend type union must follow the token change.
- Approval basis: the operator's instruction of 2026-10-24 in the tui session, which directed this change and its AI-backed approach.
