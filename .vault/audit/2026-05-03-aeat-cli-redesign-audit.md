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

## Cycle 2 — 2026-05-03

CLI-REDESIGN-007 | RESOLVED | LOW | Duplicate `PdfFilingImportError` class identity
A parallel-agent refactor left two `PdfFilingImportError` class
definitions: one in `src/aeat/adapters/inbound/pdf/_errors.py` and
one in `src/aeat/domain/justificante/_errors.py`. Both subclass
`AeatError`, so both required a registry entry — but only one was
present, and which one was registered alternated between cycles.
Cycle 2 consolidates: the canonical class lives in
`aeat.domain.justificante._errors`, and
`aeat.adapters.inbound.pdf._errors` is a re-export only. The
error registry points at the canonical domain path.

CLI-REDESIGN-008 | RESOLVED | LOW | Missing `CasillaDataType` re-export from `domain.schema._enums`
The `_enums.py` docstring documented a re-export of
`CasillaDataType` from `aeat.domain.casillas.models`, but the
actual re-export had been removed during a parallel refactor.
Three modules under `aeat.domain.schema` (`_models.py`,
`_cache.py`, the schema `__init__.py`) imported it from this
module and failed at collection time. Restored the re-export
inside `_enums.py` and added `__all__` so future churn won't
silently drop it again.

Cycle 2 progress on the original 5 open gaps:
* CLI-REDESIGN-001 (ledger schema) — no backend movement;
  still OPEN.
* CLI-REDESIGN-002 (invoice schema) — no backend movement;
  still OPEN.
* CLI-REDESIGN-003 (profile registry) — no backend movement;
  still OPEN.
* CLI-REDESIGN-004 (declaration export/verify) — no backend
  movement; still OPEN.
* CLI-REDESIGN-005 (import diagnostics) — no backend movement;
  still OPEN.

The 5 open gaps remain the priority; cycle 3 will check whether
the implementation team has begun any of them and re-verify the
full backend test sweep.

## Cycle 3 — 2026-05-03

CLI-REDESIGN-003 | PARTIALLY-RESOLVED | HIGH | `ProfileKey` registry now lives in the domain layer
The schema-backed profile editor mandated by the v6 ADR needs a
canonical key registry. Cycle 3 ships a strict pydantic
:class:`ProfileKey` record plus a closed `PROFILE_KEYS` tuple in
`src/aeat/domain/profile/_keys.py`, exposed from
`aeat.domain.profile`. Each entry carries a multilingual
:class:`Translatable` description (Spanish authoritative, English
/ Catalan / Hungarian filled out per the multilingual contract).
Helper functions :func:`get_profile_key`,
:func:`required_profile_keys`, and :func:`optional_profile_keys`
cover the v6 candidate's `list-keys` / `get` / `validate` use
cases. Eight unit tests in `test_keys.py` lock the registry shape
(uniqueness, requirement partition, blank-key rejection,
authoritative-Spanish enforcement). The CLI still owns the
hardcoded `_PROFILE_KEY_ROWS` tuple in
`src/aeat/entrypoints/cli/__init__.py`; the implementation team
removes that on the CLI side and routes through the domain
helpers — the audit prompt forbids editing CLI code.

Cycle 3 progress on remaining gaps:
* CLI-REDESIGN-001 (ledger schema) — no movement; OPEN.
* CLI-REDESIGN-002 (invoice schema) — no movement; OPEN.
* CLI-REDESIGN-003 (profile registry) — domain helper landed;
  PARTIALLY-RESOLVED pending CLI migration.
* CLI-REDESIGN-004 (declaration export/verify) — no movement; OPEN.
* CLI-REDESIGN-005 (import diagnostics) — no movement; OPEN.

Backend full sweep at cycle start: 3746 passed, 5 skipped
(`src/aeat/domain` + `src/aeat/application` + `src/aeat/core`).

## Cycle 4 — 2026-05-03

CLI-REDESIGN-005 | PARTIALLY-RESOLVED | MEDIUM | Typed `LedgerImportDiagnostic` record landed in the application layer
The v6 candidate's `aeat app ledger import PATH --provider PROVIDER --verify` flow needs structured diagnostics covering four
closed kinds: original-file, gap, duplicate, parser. Cycle 4 ships
the typed surface that the CLI implementation team's renderers can
target without waiting for the full use-case orchestration.

`src/aeat/application/transactions/_diagnostics.py` exposes a strict
pydantic :class:`LedgerImportDiagnostic` record, the
:class:`LedgerImportDiagnosticKind` closed enum (matching the v6
ADR vocabulary verbatim), :class:`LedgerImportDiagnosticSeverity`
(info / warning / error), a `build_ledger_import_diagnostic`
factory, and seven unit tests that lock the kind / severity
enumerations, the multilingual-message contract, and the frozen-
record invariants.

The orchestration use-case that fans the four diagnostic kinds out
across an actual import run is the next layer; it depends on a
duplicate-detection helper, a calendar-gap analyser, and an
original-file fingerprint comparator that the implementation team
can land incrementally on top of this typed scaffold without
breaking the CLI's renderer contract.

Cycle 4 progress on remaining gaps:
* CLI-REDESIGN-001 (ledger schema) — OPEN.
* CLI-REDESIGN-002 (invoice schema) — OPEN.
* CLI-REDESIGN-003 (profile registry) — PARTIALLY-RESOLVED on the
  domain side from cycle 3.
* CLI-REDESIGN-004 (declaration export/verify) — OPEN.
* CLI-REDESIGN-005 (import diagnostics) — PARTIALLY-RESOLVED via
  the typed surface; orchestration use-case still OPEN.

## Cycle 5 — 2026-05-03

CLI-REDESIGN-004 | PARTIALLY-RESOLVED | MEDIUM | Typed export receipt + verify verdict landed in `aeat.application.filing`
The v6 candidate's `aeat app declaration export --output PATH` and
`aeat app declaration verify --file PATH` flows need a strict typed
return value the CLI can render and persist. Cycle 5 ships the typed
surface so the CLI renderers and tests can target a stable schema
without waiting for the orchestration-layer wiring on top of the
existing `aeat.adapters.outbound.aeat.export._formats` serialisers.

`src/aeat/application/filing/_export.py` exposes a strict pydantic
:class:`DeclarationExportResult` (draft id, modelo, period, format,
output path, byte size, lowercase hex SHA-256 digest, exported-at
timestamp, multilingual narrative) plus a
:class:`DeclarationVerifyResult` (draft id, file path, closed
:class:`DeclarationVerifyVerdict` of `match` / `drift` / `missing`,
mismatched casillas tuple, optional digest, verified-at timestamp,
multilingual narrative). :class:`DeclarationExportFormat` is a closed
enum currently exposing `fichero-boe`; new on-disk wire formats land
as additional values. Thirteen unit tests in `test_export.py` lock the
enum vocabularies, the digest hex / case validators, the
authoritative-Spanish narrative contract, the frozen-record invariant,
and the rejection of blank or padded casilla identifiers.

The orchestration use-cases that turn an approved
:class:`aeat.domain.filing.FilingDraft` into a fichero-BOE payload on
disk and then re-parse the file for the verify path are the next
layer; they live on top of the adapter-level
`aeat.adapters.outbound.aeat.export._formats.serialise` and
`deserialise` primitives that already exist, plus a casilla-diff
helper. None of that touches the CLI facade and all of it can land
incrementally on top of the typed scaffold without breaking the CLI
renderer contract.

Cycle 5 progress on remaining gaps:
* CLI-REDESIGN-001 (ledger schema) — OPEN.
* CLI-REDESIGN-002 (invoice schema) — OPEN.
* CLI-REDESIGN-003 (profile registry) — PARTIALLY-RESOLVED on the
  domain side from cycle 3; CLI migration still OPEN.
* CLI-REDESIGN-004 (declaration export/verify) — PARTIALLY-RESOLVED
  via the typed surface; orchestration use-case still OPEN.
* CLI-REDESIGN-005 (import diagnostics) — PARTIALLY-RESOLVED via
  the typed surface from cycle 4; orchestration use-case still OPEN.

Backend full sweep at cycle close: 3774 passed, 5 skipped
(`src/aeat/domain` + `src/aeat/application` + `src/aeat/core`,
`-m "not live"`).

## Cycle 6 — 2026-05-03

CLI-REDESIGN-009 | PARTIALLY-RESOLVED | MEDIUM | Typed `DeclarationCalculateSummary` for the bare-`calculate` flow
The v6 ADR mandates that bare `aeat app declaration calculate` prints a
compact summary table, blocker counts, warnings, and the next action,
and that it shows repair hints instead of succeeding silently when the
inputs are unresolved. Until cycle 6 the application layer exposed
`build_draft` (which returns a `FilingDraft` with mixed-severity
findings) but no typed surface the CLI could render against; the
next-action heuristic (review / approve / export / refresh-approval /
amend / resolve-blockers) was therefore not project-owned and risked
diverging across renderer reimplementations.

`src/aeat/application/filing/_calculate.py` exposes a strict pydantic
:class:`DeclarationCalculateSummary` (draft id, modelo, period, status,
blocker / warning / info counts, closed
:class:`DeclarationCalculateNextAction`, multilingual repair hints,
multilingual narrative, calculated-at timestamp) plus a
:func:`summarise_calculation` factory that maps a `FilingDraft` to the
summary. The next-action mapping is deterministic: any ERROR finding
routes to `resolve-blockers` regardless of status; otherwise the
status-driven walk is `READY_TO_SUBMIT → approve`, `APPROVED → export`,
`APPROVAL_STALE → refresh-approval`, downstream lifecycle (submitted /
acknowledged / rejected / amended / cancelled) → `amend`, anything
else → `review`. A model-validator enforces the v6 silent-blocker
prohibition: `repair_hints` must be non-empty when `next_action` is
`resolve-blockers` and must be empty otherwise. Fourteen unit tests in
`test_calculate.py` lock the enum vocabulary, the routing matrix, the
finding-count tabulation, the i18n contract, and the frozen-record
invariant.

This scaffold lives entirely in the application layer; it does not
modify any domain record, does not touch the CLI facade, and binds
purely to the existing `FilingDraft` / `FilingDraftStatus` /
`FilingFindingSeverity` types. The orchestration layer that synthesises
truly upstream-aware repair hints from the casilla catalogue is the
next layer; this scaffold lets the CLI render bare-calculate output
against a stable schema today.

Cycle 6 progress on remaining gaps:
* CLI-REDESIGN-001 (ledger schema) — OPEN; the in-flight CLI work
  under `src/aeat/application/user_cli.py` carries an emerging
  `LedgerReviewRecord` / `LedgerSplit` / `WorkflowEvent` review-state
  layer that overlays the immutable `Transaction` record. The schema
  fields (skip, split, comments, reference, document.path, modelo,
  review.history) are largely covered there; the remaining backend
  work is the persistence / migration / hash-anchor wiring.
* CLI-REDESIGN-002 (invoice schema) — OPEN; same pattern. The
  `InvoiceReviewRecord` overlay covers comments / fields / history;
  `iva.category`, `retention.rate`, `retention.amount`, `payment.id`
  remain canonical-Invoice-record gaps.
* CLI-REDESIGN-003 (profile registry) — PARTIALLY-RESOLVED on the
  domain side from cycle 3; the in-flight `ProfileRecord` workflow
  layer covers the editable values; the CLI migration is in motion.
* CLI-REDESIGN-004 (declaration export/verify) — PARTIALLY-RESOLVED
  via cycle 5's typed surface; orchestration use-case still OPEN.
* CLI-REDESIGN-005 (import diagnostics) — PARTIALLY-RESOLVED via the
  cycle-4 typed surface; orchestration use-case still OPEN.
* CLI-REDESIGN-009 (declaration calculate summary) —
  PARTIALLY-RESOLVED via this cycle's typed surface; the upstream-
  aware repair-hint synthesis is the next layer.

Backend full sweep at cycle close: 3788 passed, 5 skipped
(`src/aeat/domain` + `src/aeat/application` + `src/aeat/core`,
`-m "not live"`).
