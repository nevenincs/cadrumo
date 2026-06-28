---
tags:
  - '#adr'
  - '#bucket-search'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-cli-workflow-redesign-adr]]"
  - "[[2026-06-03-cli-workflow-redesign-research]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - '[[2026-06-04-bucket-search-research]]'
---

# `bucket-search` adr: `BucketMaintenanceService search verb scoping` | (**status:** `accepted`)

## Problem Statement

The composition-pattern ADR `2026-06-03-cli-workflow-redesign-adr` lands the
`browse`, `delete`, and `rename` verbs of `BucketMaintenanceService` over
existing single-writer primitives, and identifies `search` as the only
maintenance verb without prior authority. The 2026-05-15 amendment to the
bucket ADR locks the method signature as
`search(query, scope=None) -> ranked rows with match metadata` but leaves
every substantive design question open: query syntax, search scope,
decryption-cost bounding, ranking, and redaction policy. This ADR scopes
the verb so an implementation Step can open without rediscovering the
design space.

Searching encrypted secure-object storage is not free: every payload that
contributes to the result set must be decrypted. Naively iterating every
namespace's records to substring-match a query string is a worst-case
cryptographic load proportional to the bucket's total stored data. A
search surface that does not bound this cost shifts the decryption load
onto every operator action that hits the verb, including accidental
typos.

## Considerations

The search verb sits between three pre-existing surfaces. The
`namespace`-level inventory landed by `browse` enumerates structure
without decryption; the `list_records` enumeration on
`SecureObjectRepository` decrypts every row in a namespace; the
domain-typed records exposed by each per-domain repository (ledger,
modelo, profile) carry the natural fields an operator would want to
search. A `search` verb that bypasses the domain repositories and
reaches directly into `secure_objects` would be searching against
ciphertext payloads after wholesale decryption — slow, redaction-blind,
and tied to the storage envelope rather than the domain shape.

The natural-search axis on this codebase is the per-domain repository's
existing read surface. The ledger has `list_all` over
`LedgerTransaction`; modelo work has work-unit catalogues per modelo;
the bucket-event history has its own indexed query surface
(`for_object`, `filters by event_type`). An operator search query like
"all 2024 payments to NIF X12345678" is naturally satisfied by routing
to the ledger repository's existing filters, not by spelunking the
secure-objects table.

The `scope` parameter on the ADR signature is the lever for this
routing. A scope value names which domain's read surface answers the
query; the search verb becomes a thin dispatcher rather than a parallel
search engine. Defaulting `scope` to `None` lets the verb refuse with
an enumerable list of accepted scopes rather than silently picking one.

## Constraints

The search verb MUST NOT bypass per-domain `SensitivityClass` redaction.
Each per-domain repository's read surface already applies the redaction
policy its records carry; the search verb consumes the redacted reads
and surfaces them to the operator. A search verb that touched
`secure_objects` directly would have no domain-level redaction context.

The search verb MUST NOT introduce a new decryption-cost path. Every
decryption it triggers is one the operator could have triggered via
the per-domain `aeat app ledger list` / `aeat app modelo work list` /
equivalent verbs. The search verb is a routing convenience; it does
not unlock data the operator could not already see.

The verb MUST surface its accepted scopes when the operator passes an
unknown scope. A bare "value invalid" refusal would violate the
`aeat-architecture-boundaries` rule's first-instructive-surface
mandate. The scope catalogue lives in a closed enum.

## Implementation

Implementation lands behind this ADR as a new follow-up plan Step under
W77.P370 of the CLI workflow redesign plan. The shape:

- A new closed enum `BucketSearchScope` under
  `src/aeat/application/bucket_maintenance/_search.py` enumerating
  accepted scope values. The MVP scope set is
  `{LEDGER_TRANSACTION, MODELO_WORK_UNIT, BUCKET_EVENT_HISTORY}` —
  each value names a per-domain repository whose existing read
  surface answers a meaningful operator question. Other domains
  (payable invoices, evidence attachments) join later as their read
  surfaces stabilise.

- `BucketMaintenanceService.search(SearchBucketCommand)` dispatches on
  the scope value: each branch calls the matching per-domain
  repository's existing list / filter method with the query string,
  applies the scope-specific filter shape (substring match on display
  fields for ledger, work-unit-name pattern for modelo work,
  event-type prefix for history), and returns the ranked rows as a
  closed `SearchBucketResultRow` Pydantic record carrying the
  domain-typed payload reference, the matching field, and the
  match-position metadata.

- Pydantic command + result contracts at
  `_contracts.py` follow the existing pattern: `SearchBucketCommand`
  takes `bucket_id: BucketId`, `query: str` (min_length=1), `scope:
  BucketSearchScope`. The contract refuses an unknown scope at
  pydantic-validation time (closed enum), so the CLI surfaces the
  accepted set via Click's choice rendering per the
  architecture-boundaries CLI-boundary discipline.

- Ranking is recency-first (latest-`written_at` first) within each
  scope for the MVP. A weighted ranking that mixes match position
  and document age is a future enhancement; the recency-first MVP
  is non-arbitrary and matches how operators typically scan a fresh
  ledger for recent rows.

- Pagination uses the same offset/limit shape the `browse` verb
  will gain in its key-level follow-up Step, so the two read verbs
  share one cursor schema.

- The verb emits no bucket event (read-only).

## Rationale

Routing search through per-domain repositories preserves the
single-writer / single-reader contracts the domain layer already
holds. A monolithic `secure_objects`-direct search would re-implement
the redaction and field-projection that every per-domain read
surface already gets right; this ADR keeps the routing thin so the
domain surfaces stay authoritative.

The closed scope enum mirrors the architectural-boundaries discipline
the rest of the CLI applies to closed value sets: the operator's
first-instructive surface is Click's choice rendering of the enum
members; a runtime "value invalid" refusal carries the accepted set
in its message. This is the same shape that
`OutputLanguage` and `StandardPeriodCode` use elsewhere.

The recency-first MVP ranking is intentionally simple. Operator
research on this codebase has not surfaced a workflow that demands a
weighted relevance score; the recency-first default matches how
operators read ledger / work-unit listings today (most-recent-first
in `list` verbs). Upgrading to a weighted ranking is a downstream
refinement once an operator workflow demands it.

## Consequences

The search verb becomes implementable as one focused commit per
scope value once a multi-bucket fixture lands: each scope adds one
dispatch branch in the service, one set of contract tests against
the matching per-domain repository, and one CLI registration. The
verb can ship with a single scope (e.g. `LEDGER_TRANSACTION`) and
grow as new domains stabilise; the closed-enum dispatcher rejects
unknown scopes safely.

The decision NOT to search secure-object ciphertext directly forecloses
one design alternative: a true full-text search that would not require
per-domain routing. That alternative is rejected here as too expensive
(O(every-row-decryption) per query) and redaction-blind. If a future
requirement emerges for cross-domain free-text search, it lands as a
separate verb (`aeat config bucket grep` or similar) with its own ADR
and cost-bounding strategy.

The MVP scope set excludes some domains. Operator workflows that
search across `purchase_invoice_evidence` or `attachment` rows must
wait for those domains' search-aware read surfaces. This is honest
gap-disclosure rather than a half-baked search-everything verb.

## Codification candidates

- **Rule slug:** `search-routes-through-domain-repositories`.
  **Rule:** A new search surface MUST route its decryption-bearing
  queries through per-domain repository read surfaces, never against
  the `secure_objects` table directly. The per-domain repository owns
  the redaction policy and the field-projection contract; a search
  verb is a thin scope-dispatcher, not a parallel reader.

  This codification candidate is held until the search verb actually
  lands. The discipline binds future search-surface authors whether
  or not this specific ADR's MVP scope set survives.
