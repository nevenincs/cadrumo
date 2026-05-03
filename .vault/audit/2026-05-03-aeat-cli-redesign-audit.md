---
tags:
  - '#audit'
  - '#aeat-cli-redesign'
date: '2026-05-03'
related:
  - '[[2026-05-02-aeat-cli-redesign-adr]]'
  - '[[2026-05-02-aeat-cli-redesign-reference]]'
  - '[[2026-04-24-aeat-cli-wireframe-adr]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `aeat-cli-redesign` audit: backend-library readiness for v6 candidate

## Scope

This audit checks the backend-library coverage required by the v6
candidate command surface. The CLI facade is explicitly out of
scope — the goal is to surface gaps that the CLI implementation
team will hit when building `aeat setup` and `aeat app` against the
current `domain` / `application` / `adapters` / `core` packages. The
v6 ADR explicitly defers the implementation plan until backend
audits cover auth providers, profile registry, ledger schema,
invoice metadata, declaration lifecycle, import diagnostics, and
correction terminology. This audit focuses on the structured-data
side of those backend audits.

## Findings

CLI-REDESIGN-001 | OPEN | HIGH | Ledger record schema is incomplete vs the v6 candidate
The v6 reference packet enumerates 19 ledger target fields. Today's
`Transaction` record in `src/aeat/domain/transactions/_models.py`
covers `transaction_id`, `raw.date`, `raw.description`,
`raw.amount`, `direction`, `business_classification` (semantic alias
of `status`), `business_pct` (semantic alias of `business.share`),
`invoice_id`, `category_id`, `notes`, and
`classification_history`. The following v6 fields have no backend
representation and the CLI agents will block on them:
`source.import.id` (no import-batch identity ties a transaction
back to its import run), `skip` (no boolean flag plus reason audit
trail; the ADR rejects an exclude/restore command pair in favour
of an `--skip` edit), `reference` (free-text user reference),
`document.path` (attached supporting-file path), `modelo` (modelo
association so a row's tax destination is queryable without a
calculation), and `split.metadata` (preserves source identity for
mixed-use rows split into business + personal shares; the ADR
mandates split shares add to 1.0 and a `--split clear` reset path).
The existing `notes` field overlaps with the ADR's `comments` slot
but the field name divergence will surface when CLI agents render
the column. The existing `classification_history` partially
covers `review.history` but the ADR's review surface includes
edits beyond classification (skip toggles, split changes, reference
edits) which are not currently history-tracked.

CLI-REDESIGN-002 | OPEN | HIGH | Invoice record schema is incomplete vs the v6 candidate
The v6 reference packet enumerates 17 invoice target fields. The
`Invoice` record in `src/aeat/domain/invoices/_models.py` covers
`invoice_id`, `kind`, `payment_status` (semantic alias of
`status`), `issued_at` (semantic alias of `issue_date`),
`counterparty_*` (covers `counterparty`), `base_total` (covers
`base`), `iva_total` (covers `iva.amount` aggregate),
`grand_total`, `lines`, `linked_transaction_ids` (partial coverage
of `payment.id`), and `notes` (semantic alias of `comments`). The
following v6 fields have no backend representation:
`iva.category` (per-invoice IVA category — distinct from
per-line `category_id`), `retention.rate`, `retention.amount`
(no IRPF retention modelling at the invoice level — required for
M111 / M115 / M123 reconciliation), `payment.id` (a single typed
payment-link id, distinct from the multi-id
`linked_transaction_ids` aggregate), `document.path`,
`reference`, and `review.history`.

CLI-REDESIGN-003 | OPEN | HIGH | Profile data is not schema-backed in the domain layer
The v6 ADR mandates a schema-backed profile editor exposing
`list-keys`, `get`, `set`, `unset`, and `validate`. Today the
profile-key registry lives as a hardcoded tuple
`_PROFILE_KEY_ROWS` inside `src/aeat/entrypoints/cli/__init__.py`
— pure CLI code with no domain-layer mirror. The CLI rework
team will need to migrate the registry into
`src/aeat/domain/profile/` (e.g., as a `ProfileKey` pydantic
record + tuple of canonical entries) and add validation primitives
that the new `aeat setup profile validate` command can call. The
v6 candidate also requires a profile-data record (active profile
selection, schema-backed values, validation state). The current
domain layer exposes only a `TaxpayerProfile` enum from
`src/aeat/domain/modelos/_categories.py`; there is no profile-data
record class with persistence and validation.

CLI-REDESIGN-004 | OPEN | MEDIUM | Declaration lifecycle export / verify primitives are missing
The application/filing surface covers `build_draft` (calculate),
`validate_draft`, `approve_draft` / `unapprove_draft`,
`refresh_review_status`, plus `FilingApprovalStaleReason` for
the staleness contract. The v6 candidate further requires:
`declaration export --output PATH` (write a local AEAT-compatible
file) and `declaration verify --file PATH` (verify a previously
exported file against the approved local draft). The current
verify surface in `src/aeat/application/verification/_verify.py`
is the AEAT-side declaracion verifier and does not match the
v6 contract that compares an exported local file against the
approved draft. There is no `export_draft(...)` primitive in
`src/aeat/application/filing/__init__.py`; the `aeat.adapters.outbound.aeat.export`
package exists but no application-layer entry binds it to a
`FilingDraft`.

CLI-REDESIGN-005 | OPEN | MEDIUM | Ledger import diagnostics are not structured for the CLI
The v6 candidate exposes `aeat app ledger import PATH --provider PROVIDER --verify --source PATH --verbose` and emits original-file
checks, gap checks, duplicate checks, and parser checks as
diagnostic output. The current financial-ingest layer in
`src/aeat/adapters/inbound/financial/providers/` parses the
input file into `RawTransaction` records but does not emit
structured diagnostic findings for the four categories the v6
ADR enumerates. There is no application-layer
`import_ledger_with_diagnostics(...)` that returns a typed
findings tuple the CLI can render. The
`src/aeat/application/filing/_import.py` module imports
justificantes (filed AEAT submissions), not ledger transaction
files, and does not satisfy this requirement.

CLI-REDESIGN-006 | RESOLVED | LOW | Inbound-pdf import error has been restored
The collection-time error in `src/aeat/adapters/inbound/pdf/_errors.py`
(empty body after a parallel-agent refactor) plus the stale
registry pointer in `src/aeat/core/errors/_registry.py` were both
restored on 2026-05-03 inside this audit cycle. `PdfFilingImportError`
now subclasses `AeatError` again, the registry entry points at the
canonical adapter path, and the corpus alignment test suite is
back to 28 / 28 passing. Documenting in case the CLI team sees
the same error pattern after a future refactor.

## Recommendations

The five primary gaps (`CLI-REDESIGN-001` through
`CLI-REDESIGN-005`) should land as backend prep work in this
order: ledger schema (blocks ledger import + edit + review),
invoice schema (blocks invoice review + edit + match), profile
registry (blocks setup profile commands), declaration
export/verify primitives (blocks declaration export + verify),
import diagnostics (blocks ledger import --verify). All five
are pure-domain or application-layer additions; they do not
touch the CLI facade. Each should ship with strict pydantic
models, full multilingual error catalogue entries, and unit
tests that cover the shape the CLI commands will read.

The v6 ADR's "Open Approval Questions" section lists eight
items that gate implementation. Those questions should drive
the per-finding decision sequence — for example,
`CLI-REDESIGN-003` cannot be detailed until the ADR's "Which
profile keys are required for first implementation?" question
is closed.

This audit is a single-cycle snapshot. The hourly recurring
audit job will replay this scope and append delta findings as
the backend evolves.
