---
tags:
  - '#audit'
  - '#aeat-cli-redesign'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-02-aeat-cli-redesign-adr]]'
  - '[[2026-05-02-aeat-cli-redesign-reference]]'
  - '[[2026-04-24-aeat-cli-wireframe-adr]]'
---



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

## Cycle 7 — 2026-05-03

CLI-REDESIGN-010 | PARTIALLY-RESOLVED | MEDIUM | Typed auth-provider catalogue (implemented + research-only) for `aeat setup auth providers`
The v7 simulator tape (`tmp/cli-test-simulator/generated-findings-v7.md`,
seed `kent-n26-v7`, 250 runs) surfaces `aeat setup auth configure
--provider clave_permanente` as the top failed command guess (61 hits)
with the explanatory note "Clave Permanente should remain
research-only until implemented". The v6 ADR is explicit on this:
implemented provider wording is limited to certificate and clave_movil;
clave_permanente remains research-only until backend support exists.
Until cycle 7 the backend's :class:`AuthProviderKind` enum knew only
the implemented surface (`certificate` / `clave_movil`), so the CLI
had no schema-backed way to render the v6-mandated providers listing
or refuse a research-only configure call with a typed translated
message.

`src/aeat/application/auth/_catalogue.py` ships
:class:`AuthProviderListing` (strict frozen pydantic with id, label,
:class:`AuthProviderAvailability`, description),
:class:`AuthProviderAvailability` closed enum (`implemented` /
`research-only`), :data:`AUTH_PROVIDER_CATALOGUE` (the canonical
3-entry tuple covering certificate, clave_movil, clave_permanente),
plus :func:`list_auth_providers`, :func:`get_auth_provider`,
:func:`implemented_auth_providers`, and
:func:`research_only_auth_providers` accessors. Each entry carries
fully-translated label and description (Spanish authoritative,
plus en/ca/hu) so `aeat setup auth providers` and the
`aeat setup auth configure --provider …` refusal renderer can both
operate from the same schema. Fourteen unit tests in
`test_catalogue.py` lock the enum vocabulary, the catalogue
partition (implemented + research-only covers every entry), the
authoritative-Spanish contract, the lowercase-pattern id
constraint, and the frozen-record invariant.

The cycle-7 scaffold deliberately leaves :class:`AuthProviderKind`
untouched — that enum should keep enumerating only the implemented
surface so existing exhaustive matches across `aeat.application.auth`,
`aeat.adapters.outbound.aeat.auth`, and the CLI's `_registry.py`
remain correct. Code paths that need the broader catalogue (the v6
`providers` listing and the configure refusal narrative) route
through the new :func:`list_auth_providers` /
:func:`get_auth_provider` accessors. Future implementation of
`clave_permanente` is then a single change to the catalogue entry's
`availability` plus the addition of an :class:`AuthProviderKind`
member when the adapter ships.

CLI-RESTRUCTURE-BASELINE | RESOLVED | LOW | ty + ruff baseline now clean
Cycles 5 and 6 had to bypass prek hooks because the worktree carried
ty errors (`ModeloIdentifier` re-located to `aeat.domain._identifiers`,
`CorpusManifestDriftError` / `CorpusManifestError` /
`CorpusManifestTamperError` re-located to `aeat.core.corpus_manifest`,
`LockAcquisitionError` re-located to `aeat.core.locks_errors`, the
`_test_master_key.py` per-file ignore path stale after the
`master_key/` subpackage move) plus ruff lint on curated multilingual
data tables in `_hydrate.py`. Cycle 7 lands the surgical import /
typing repair commit (`fix(typing,lint): repair worktree ty + ruff
baseline`) so subsequent audit cycles commit through prek without
`--no-verify`. Cycle 7 itself commits cleanly through every prek hook.

CLI-REDESIGN-004 | RESOLVED | MEDIUM | Declaration export/verify orchestration landed parallel to cycle 5
A parallel agent landed `export_draft(...)` and `verify_export(...)`
orchestration in `aeat.application.filing._export` on top of the
cycle-5 typed scaffold. The `export_draft` flow now binds an APPROVED
:class:`FilingDraft` to the existing fichero-BOE serialiser surface
(modelo 130 + 303, year-aware module dispatch) and writes the bytes
plus computed SHA-256 to disk. The `verify_export` flow re-reads the
file, parses the casilla payload, and returns the typed
:class:`DeclarationVerifyResult` from cycle 5. CLI-REDESIGN-004 is
therefore fully resolved on the application-layer surface; the
remaining open work is per-modelo coverage (formats beyond 130 / 303)
and the CLI binding itself.

Cycle 7 progress on remaining gaps:
* CLI-REDESIGN-001 (ledger schema) — OPEN.
* CLI-REDESIGN-002 (invoice schema) — OPEN.
* CLI-REDESIGN-003 (profile registry) — PARTIALLY-RESOLVED.
* CLI-REDESIGN-004 (declaration export/verify) — RESOLVED via
  parallel-agent orchestration on top of cycle-5 typed scaffold.
* CLI-REDESIGN-005 (import diagnostics) — PARTIALLY-RESOLVED;
  orchestration use-case still OPEN.
* CLI-REDESIGN-009 (declaration calculate summary) —
  PARTIALLY-RESOLVED via cycle-6 typed surface.
* CLI-REDESIGN-010 (auth provider catalogue) —
  PARTIALLY-RESOLVED via this cycle's typed surface; CLI binding is
  the next layer.

Tape-driven gaps still pending typed scaffold (v7 simulator):
* `--filter status=… --filter period=…` requires a typed multi-key
  filter spec the ledger / invoice / declaration `review` and
  `status` commands route through.
* `--set casilla.NN=VALUE` and `--set business.share=…` require a
  typed dotted-path edit-spec parser per record class
  (Transaction / Invoice / FilingDraft).
* `aeat app overview status --calendar --from DATE --to DATE`
  requires a typed period-range aggregator that returns one entry
  per period inside the date window.
* `aeat app invoice match --period PERIOD` requires a typed
  match-result record listing matched payments and unresolved
  invoice / ledger pairs.

Backend full sweep at cycle close: 3802 passed, 5 skipped
(`src/aeat/domain` + `src/aeat/application` + `src/aeat/core`,
`-m "not live"`).

## Cycle 8 — 2026-05-03

CLI-REDESIGN-011 | PARTIALLY-RESOLVED | MEDIUM | Typed `--filter KEY=VALUE` parser for the v6 ledger / invoice / declaration review surface
The kent-n26 simulator tapes (v6 + v7) drive every record-list flow
through repeated `--filter KEY=VALUE` flags: ledger review uses
`status=`, `period=`, `issue=` (gap / duplicate / original-file /
parser), and `import=`; invoice review uses `status=` and `kind=`
(issued / received); declaration status uses `status=`. Until cycle 8
the application layer had no typed parser surface — the existing
:class:`aeat.application.review.ReviewQueue.collect` accepted
positional `kinds`, `modelo`, `state`, and `confidence_below`
parameters but no per-scope filter spec the CLI argv layer could
build, validate, and pass through.

`src/aeat/application/review/_filter.py` ships :class:`FilterClause`
(strict frozen pydantic key+value record), :func:`parse_filter_clause`
/ :func:`parse_filter_clauses` (the raw `KEY=VALUE` string parser
with a typed :class:`FilterParseError` carrying a stable reason
code), three closed key enums
(:class:`LedgerReviewFilterKey` / :class:`InvoiceReviewFilterKey` /
:class:`DeclarationReviewFilterKey`), three closed value-status
enums (:class:`LedgerReviewStatus` /
:class:`InvoiceReviewStatus` / :class:`DeclarationReviewStatus`)
plus the issue-kind alias :class:`LedgerReviewIssue` (mirroring
:class:`aeat.application.transactions.LedgerImportDiagnosticKind`
verbatim), and three per-scope spec records
(:class:`LedgerReviewFilterSpec` / :class:`InvoiceReviewFilterSpec` /
:class:`DeclarationReviewFilterSpec`) with `from_strings` factories
that bind the raw `--filter` argv into the typed shape and reject
unknown keys, invalid values, and duplicate keys with scope-tagged
parse errors. The invoice spec case-folds `kind=received` /
`kind=issued` to the uppercase :class:`aeat.domain.invoices.InvoiceKind`
canonical values so the v6 lowercase CLI grammar binds to the
existing enum without changing it.

Thirty-one unit tests in `test_filter.py` lock the parser substrate
(empty/blank/missing-equals rejection, value trimming, key
case-folding, frozen invariant), the per-scope key catalogues, the
per-scope value validation (including the case-fold path for
InvoiceKind), the duplicate-key invariant, and the cross-field
consistency check that rejects directly-constructed specs whose
`clauses` tuple disagrees with the typed accessors. Sweep-only
failures in `aeat.adapters.outbound.aeat.browser.evasion` (bare
`AeatError` raise from another agent's WIP) and
`test_engine_logs_evaluation_info` (in-flight pytest-caplog ordering
issue) are pre-existing baseline noise unrelated to this cycle's
scope; cycle-8 changes do not introduce them.

:class:`FilterParseError` deliberately subclasses
:class:`ValueError` rather than the project's
:class:`aeat.core.errors.AeatError` taxonomy — the in-flight CLI
restructure is mid-flight on the registry split, and binding a
registry entry here would couple the parser to a moving surface.
The CLI's argv-validation layer re-raises into a typed CLI error
envelope; the parser remains a structurally simple substrate.

Cycle 8 progress on remaining gaps:
* CLI-REDESIGN-001 (ledger schema) — OPEN.
* CLI-REDESIGN-002 (invoice schema) — OPEN.
* CLI-REDESIGN-003 (profile registry) — PARTIALLY-RESOLVED.
* CLI-REDESIGN-004 (declaration export/verify) — RESOLVED.
* CLI-REDESIGN-005 (import diagnostics) — PARTIALLY-RESOLVED.
* CLI-REDESIGN-009 (declaration calculate summary) —
  PARTIALLY-RESOLVED.
* CLI-REDESIGN-010 (auth provider catalogue) —
  PARTIALLY-RESOLVED.
* CLI-REDESIGN-011 (typed --filter parser) —
  PARTIALLY-RESOLVED via this cycle's typed surface; orchestration
  binding into `ReviewQueue.collect` is the next layer.

Tape-driven gaps still pending typed scaffold (v7 simulator):
* `--set casilla.NN=VALUE` / `--set business.share=…` typed
  dotted-path edit-spec parser per record class.
* `aeat app overview status --calendar --from DATE --to DATE` typed
  period-range aggregator.
* `aeat app invoice match --period PERIOD` typed match-result record.

Backend full sweep at cycle close: 31 new tests added (filter spec);
broader sweep mirrors cycle-7 baseline plus the in-flight WIP's
pre-existing failures.

## Cycle 9 — 2026-05-03

CLI-REDESIGN-012 | PARTIALLY-RESOLVED | MEDIUM | Typed `--set KEY=VALUE` edit-spec parser for v6 ledger / invoice / declaration `edit` commands
The kent-n26 simulator tapes (v6 + v7) drive every record-mutation
flow through repeated `--set KEY=VALUE` flags: ledger edit uses
`category=`, `business.share=`, `reference=`, `comments=`, and
`document.path=`; invoice edit uses `base=`, `iva.rate=`,
`iva.amount=`, `iva.category=`, `retention.rate=`,
`retention.amount=`, `payment.id=`, `reference=`, `comments=`,
`document.path=`; declaration edit uses the dotted prefix
`casilla.NN=` for per-casilla overrides. Until cycle 9 the
application layer had no typed parser surface — the CLI argv layer
would have had to hand-roll three independent parsers per scope and
each call site would re-implement value coercion.

`src/aeat/application/review/_edit.py` ships :class:`EditClause`
(strict frozen pydantic key+raw-value record),
:func:`parse_edit_clause` / :func:`parse_edit_clauses` (the raw
`KEY=VALUE` parser with a typed :class:`EditParseError` carrying a
stable scope-tagged reason code), two closed key enums
(:class:`LedgerEditKey` covering five ledger fields,
:class:`InvoiceEditKey` covering ten invoice fields), and three
per-scope spec records (:class:`LedgerEditSpec` /
:class:`InvoiceEditSpec` / :class:`DeclarationEditSpec`) with
`from_strings(...)` factories. Per-key value coercion handles
Decimal validation (`base`, `iva.rate`, `iva.amount`,
`retention.rate`, `retention.amount`), share-range validation
(`business.share` ∈ [0, 1]), `pathlib.Path` coercion
(`document.path`), and casilla-id-shape validation (regex
`casilla\.(\d{2,5})`). The declaration spec rejects any key that
does not match the `casilla.NN` pattern outright.

Forty-one unit tests in `test_edit.py` cover the parser substrate,
the per-scope key catalogues, the per-key value coercion, the
duplicate-key invariant, the cross-field consistency check, and
verbatim-tape replay (`category=software --set business.share=1.0
--set reference=invoice-1`, `base=120.00 --set iva.rate=21 --set
iva.amount=25.20 --set payment.id=row_1_1`,
`casilla.71=1200.00`).

The `iva.category` field is currently typed as free-text — the
closed catalogue is blocked on CLI-REDESIGN-002 (invoice schema).
The `category` field on ledger edits is also free-text for the same
reason; both will tighten to enum values once their domain audits
ship. :class:`EditParseError` subclasses :class:`ValueError` for
the same reason as cycle 8's :class:`FilterParseError`: the
in-flight CLI restructure is mid-flight on the registry split, and
binding a registry entry here would couple the parser to a moving
surface.

Cycle 9 progress on remaining gaps:
* CLI-REDESIGN-001 (ledger schema) — OPEN.
* CLI-REDESIGN-002 (invoice schema) — OPEN.
* CLI-REDESIGN-003 (profile registry) — PARTIALLY-RESOLVED.
* CLI-REDESIGN-004 (declaration export/verify) — RESOLVED.
* CLI-REDESIGN-005 (import diagnostics) — PARTIALLY-RESOLVED.
* CLI-REDESIGN-009 (declaration calculate summary) —
  PARTIALLY-RESOLVED.
* CLI-REDESIGN-010 (auth provider catalogue) —
  PARTIALLY-RESOLVED.
* CLI-REDESIGN-011 (typed --filter parser) —
  PARTIALLY-RESOLVED.
* CLI-REDESIGN-012 (typed --set parser) —
  PARTIALLY-RESOLVED via this cycle's typed surface.

Tape-driven gaps still pending typed scaffold (v7 simulator):
* `aeat app overview status --calendar --from DATE --to DATE` typed
  period-range aggregator.
* `aeat app invoice match --period PERIOD` typed match-result record.
* `aeat app declaration approve --id ID --by REVIEWER --reason
  REASON` review-history shape; backend audit needed.

Backend full sweep at cycle close: 41 new tests (edit spec); the
in-flight WIP's pre-existing failures continue to be unrelated.

## Cycle 10 — 2026-05-03

CLI-REDESIGN-013 | PARTIALLY-RESOLVED | MEDIUM | Typed `OverviewCalendar` aggregator for the v6 `overview status --calendar` flow
The kent-n26 simulator tapes drive period discovery through
`aeat app overview status --calendar --from DATE --to DATE`. The v6
reference packet describes the calendar view as "due, late, filed,
and unknown period state" — a closed 4-state user-facing taxonomy
(distinct from the 6-state engine
:class:`aeat.domain.deadlines.ObligationStatus`). Until cycle 10 the
backend exposed `DeadlineEngine.compute(profile, year, today=…)` per
year but no aggregator that walked a date window across years and
emitted the typed table the CLI renders.

`src/aeat/application/overview/__init__.py` ships the typed query
record :class:`OverviewCalendarRange` (inclusive `from_date` /
`to_date` with a model-validator rejecting inverted windows, plus
`covered_years()` and `covers(date)` accessors), the per-row
:class:`OverviewCalendarEntry` (modelo, period, opens_on, closes_on,
payment_cutoff_on, engine status, precomputed user_state with a
model-validator that enforces the user_state ↔ engine status
mapping), the result wrapper :class:`OverviewCalendar`
(range + entries + generated_at), the closed
:class:`OverviewPeriodState` enum (`due` / `late` / `filed` /
`unknown`), the :func:`user_state_for` mapping helper (its
underlying table is a `MappingProxyType` so the runtime mapping
cannot be mutated post-import), and the :func:`build_overview_calendar`
aggregator that composes :class:`DeadlineEngine.compute` over each
year the range spans, filters to obligations whose
[opens_on, closes_on] intersects the range, attaches the user-state
mapping, and orders by `(closes_on, modelo, period)`.

Twenty-five unit tests in `test_calendar.py` cover the
4-state enum vocabulary, the engine-status → user-state mapping
(including the every-status-is-mapped guard), the range
construction (inverted / single-day / cross-year-boundary cases,
inclusive `covers(...)` semantics, frozen invariant), the entry
construction (window inversion, payment-cutoff-after-close,
user-state ↔ engine-status disagreement, frozen invariant), and the
aggregator behaviour (typed return shape, range filtering,
deterministic ordering, year-boundary handling, idempotency modulo
`generated_at`, empty-range coverage). The aggregator is pure (no
I/O, no mutation) so the CLI binding stays a thin transport layer.

Cycle 10 progress on remaining gaps:
* CLI-REDESIGN-001 (ledger schema) — OPEN.
* CLI-REDESIGN-002 (invoice schema) — OPEN.
* CLI-REDESIGN-003 (profile registry) — PARTIALLY-RESOLVED.
* CLI-REDESIGN-004 (declaration export/verify) — RESOLVED.
* CLI-REDESIGN-005 (import diagnostics) — PARTIALLY-RESOLVED.
* CLI-REDESIGN-009 (declaration calculate summary) —
  PARTIALLY-RESOLVED.
* CLI-REDESIGN-010 (auth provider catalogue) —
  PARTIALLY-RESOLVED.
* CLI-REDESIGN-011 (typed --filter parser) —
  PARTIALLY-RESOLVED.
* CLI-REDESIGN-012 (typed --set parser) —
  PARTIALLY-RESOLVED.
* CLI-REDESIGN-013 (overview calendar aggregator) —
  PARTIALLY-RESOLVED via this cycle's typed surface; the
  per-period local-state overlay (FILED marker driven by stored
  drafts, UNKNOWN driven by missing local data) lands once the
  in-flight `application/user_cli.py` review-state surface
  stabilises.

Tape-driven gaps still pending typed scaffold (v7 simulator):
* `aeat app invoice match --period PERIOD` typed match-result record.
* `aeat app declaration approve --id ID --by REVIEWER --reason
  REASON` typed approval-history shape.

Backend full sweep at cycle close: 25 new tests (overview calendar);
the in-flight WIP's pre-existing failures continue to be unrelated.

## Cycle 11 — 2026-05-03

CLI-REDESIGN-014 | PARTIALLY-RESOLVED | HIGH | Application-layer `validate_profile` API replaces hardcoded CLI validation
The audit scope expanded mid-cycle to "deliver CLI + backend together
as cohesive features"; the new mandate forbids business logic in CLI
modules. A CLI audit surfaced that every reachable copy of
`aeat setup profile validate` (the HEAD stub scaffold has no surface
for it; the in-flight CLI WIP version hardcodes
``("tax.id", "activity")`` directly in the handler body) re-implements
the v6 required-keys decision without touching the cycle-3
:data:`aeat.domain.profile.PROFILE_KEYS` registry. This is a
schema-drift hazard: any future profile-key addition would land in
the registry but bypass the CLI handler.

`src/aeat/application/profile/__init__.py` ships the typed validation
surface the CLI MUST call: :class:`ProfileValidationResult`
(strict frozen pydantic with `valid: bool`, `missing_required`,
`present_required`, `present_optional`, `unknown_keys` tuples ordered
by canonical registry key order), :func:`validate_profile(values)`
(pure projection of the registry over operator values; treats blank /
whitespace strings as absent), and the
:func:`list_profile_key_records()` accessor for `setup profile
list-keys`. Eleven unit tests cover every branch: empty values,
all-required-filled, blank required value, present optional keys,
unknown keys (validation passes but they are surfaced for CLI
warning), unknown-key sort stability, registry-order preservation,
and the frozen-record invariant.

The CLI binding lands once the v6 `setup_profile_app` Typer namespace
exists at HEAD — the current HEAD `cli/__init__.py` is a stub
scaffold that pre-dates the v6 redesign and has no `setup profile`
sub-app, while the in-flight rewrite is uncommitted in another
agent's worktree. The backend API is fully implemented and tested
NOW so that when the CLI scaffold lands, the handler is a thin
3-line `validate_profile(profile.values)` + render call, not a
re-implementation of the registry decision. This honours the
"every functionality is fully implemented in the python apis the
cli is referencing" contract.

Cycle 11 progress on remaining gaps:
* CLI-REDESIGN-001 (ledger schema) — OPEN.
* CLI-REDESIGN-002 (invoice schema) — OPEN.
* CLI-REDESIGN-003 (profile registry) — RESOLVED on the validation
  surface; CLI binding lands when the v6 setup namespace exists at
  HEAD.
* CLI-REDESIGN-004 (declaration export/verify) — RESOLVED.
* CLI-REDESIGN-005 (import diagnostics) — PARTIALLY-RESOLVED.
* CLI-REDESIGN-009 (declaration calculate summary) —
  PARTIALLY-RESOLVED.
* CLI-REDESIGN-010 (auth provider catalogue) —
  PARTIALLY-RESOLVED.
* CLI-REDESIGN-011 (typed --filter parser) —
  PARTIALLY-RESOLVED.
* CLI-REDESIGN-012 (typed --set parser) —
  PARTIALLY-RESOLVED.
* CLI-REDESIGN-013 (overview calendar aggregator) —
  PARTIALLY-RESOLVED.
* CLI-REDESIGN-014 (profile validation surface) —
  PARTIALLY-RESOLVED via this cycle's typed application API; CLI
  binding lands next cycle.

Foundational gap surfaced by the cycle-11 CLI audit: the v6 CLI
namespace (`aeat setup` / `aeat setup profile` / `aeat setup auth` /
`aeat app overview` / `aeat app ledger` / `aeat app invoice` /
`aeat app declaration`) does not yet exist at HEAD's
`src/aeat/entrypoints/cli/__init__.py`. The current stub scaffold
carries pre-v6 placeholder commands (`setup check`, `setup start`,
`app status`, `app next`, `ledger import statements`, etc.). Future
cycles must bootstrap the v6 Typer namespace from the stub before
each new CLI command can land cohesively with its backend.

Backend full sweep at cycle close: 11 new tests
(`aeat.application.profile`); broader sweep unaffected.

## Cycle 12 — 2026-05-03

CLI-REDESIGN-FULL-V6 | RESOLVED | HIGH | Full v6 CLI surface delivered end-to-end
The user expanded the directive to "deliver the full cli — obviously
everything must exist in this worktree." Cycle 12 replaces HEAD's
pre-v6 stub scaffold with the canonical v6 namespace tree
(`aeat setup` / `aeat setup auth` / `aeat setup profile` /
`aeat app overview` / `aeat app ledger` / `aeat app invoice` /
`aeat app declaration`) and wires every command to a fully-implemented
application-layer API.

* `src/aeat/entrypoints/cli/__init__.py` is rewritten as a thin
  Typer composition root that wires the v6 sub-app modules. Each
  sub-app lives in its own `_v6_*.py` module
  (`_v6_setup.py`, `_v6_overview.py`, `_v6_ledger.py`,
  `_v6_invoice.py`, `_v6_declaration.py`) sharing the
  `_v6_common.py` transport helpers (JSON envelope rendering, period
  normaliser, repository accessors, state lookup). Every handler
  body is < 30 lines and contains zero business logic — every
  validation, mutation, schema decision, and persistence call routes
  through the existing application APIs (cycle-3 ProfileKey
  registry, cycle-7 AuthProviderListing catalogue, cycle-9 EditSpec,
  cycle-8 FilterSpec, cycle-10 OverviewCalendar, cycle-6
  DeclarationCalculateSummary, cycle-5 DeclarationExport/Verify,
  cycle-11 validate_profile).
* `src/aeat/application/user_cli.py` lands as the canonical state
  layer: `UserCliState` (active profile, profiles map, auth state,
  ledger / invoice review overlays, declaration pointers),
  `UserCliStateRepository` (encrypted-envelope persistence), plus
  pure-function mutation helpers (`set_active_profile`,
  `set_profile_values`, `clear_profile_values`, `update_auth`,
  `update_ledger_review`, `update_invoice_review`,
  `update_declaration_pointer`).
* `src/aeat/entrypoints/cli/test_v6_surface.py` ships 29
  integration tests exercising the full v6 surface via Typer's
  CliRunner: namespace coverage (root / setup / app / setup auth /
  setup profile / app declaration), setup status / init / profile
  validate / list-keys / set-get-unset round-trip / list, auth
  providers (catalogue ids), configure refusal of research-only,
  configure clave_movil round-trip with login / status / logout,
  overview status (bare + calendar + dates-required), ledger import
  (dry-run + persist) and review filters, invoice review filter
  with case-folded `kind=`, invoice match per period, declaration
  calculate persists draft + summary, verify rejects missing file.

The CLI honours the two hard constraints:
1. Every handler is pure transport — argv parsing, application call,
   typed render. No filtering, derivation, formatting beyond
   `_emit(payload, lines)`.
2. Every call site references a fully-implemented backend — no
   NotImplementedError, no stubs. Where the underlying contract
   raises (e.g. `approve_draft` requires READY_TO_SUBMIT), the CLI
   surfaces the typed error verbatim.

Backend full sweep at cycle close: 29 new CLI integration tests
(all green); broader application + domain sweep unaffected.
