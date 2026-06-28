---
tags:
  - "#adr"
  - "#transaction-catalogue"
date: "2026-04-14"
modified: '2026-04-14'
related:
  - "[[2026-04-14-transaction-catalogue-research]]"
  - "[[2026-04-13-p2a-financial-provider-adr]]"
---

# `transaction-catalogue` adr: `immutable-transaction-wrapper-and-catalogue` | (**status:** `accepted`)

## Problem Statement

Issue `#74` must introduce a durable transaction catalogue at the T1/T2 seam without redefining the already-merged `RawTransaction` contract, without importing unmerged sibling packages, and without weakening the provenance guarantees that the TDP requires.

## Considerations

- `RawTransaction` is already the T1 public boundary on `main` and is strict, frozen, and provenance-rich.
- The issue’s hash input names do not exactly match the merged upstream shape. The implementation must map the requested `(provider_id, value_date, amount, narrative)` tuple onto the live fields available on `RawTransaction`.
- Invoice and tax-category subpackages are not yet on `main`, so the transaction package cannot hard-import their runtime types.
- The transaction package needs both an immutable in-memory API and a practical persistence/CLI surface now, without pre-empting downstream enrichment and classification engines.

## Constraints

- Public API must be imported from `aeat.domain.financial.transactions` only.
- Every persisted and boundary-crossing structure must be strict pydantic v2; closed sets must use `enum.StrEnum`.
- Errors must inherit from `aeat.core.errors.AeatError`, and logging must use `aeat.core.logging.get_logger(__name__)`.
- The wrapped `raw` record must remain verbatim and never be mutated in place.

## Implementation

- Create `src/aeat/domain/financial/transactions/` with a public `__init__.py` and private underscored modules for enums, models, persistence, service functions, CLI helpers, and typing stubs.
- Define `TransactionDirection` and `BusinessClassification` as `StrEnum` values.
- Define `Transaction` as a strict frozen pydantic model embedding `raw: RawTransaction` and storing the issue-mandated classification/linking fields.
- Generate catalogue transaction IDs with a deterministic SHA-256 over the canonical tuple `(raw.transaction_id, raw.value_date or raw.booked_date, raw.amount, raw.description)`. This preserves the issue’s intent while matching the merged upstream contract on `main`.
- Define `TransactionCatalogue` as a strict pydantic model wrapping `dict[str, Transaction]`, plus helper constructors and immutable update helpers so duplicate logical IDs are rejected and caller-facing operations return fresh catalogue instances.
- Keep invoice/category interoperability at typing level only through internal `Protocol` placeholders in `_stubs.py`; runtime fields remain `str | None`.
- Persist the entire catalogue to one JSON file with atomic temp-file replacement.
- Extend `aeat financial` with a nested `txs` Typer app that loads/saves the on-disk catalogue in the configured transactions directory.

## Rationale

- Wrapping `RawTransaction` instead of copying or normalizing it preserves the provenance chain exactly as delivered by T1 and keeps downstream stages auditable.
- An immutable `Transaction` plus immutable-return catalogue operations make provenance integrity easier to reason about than in-place mutation.
- A SHA-256 digest over a canonical text payload is simple, deterministic, and collision-resistant enough for stable catalogue keys while satisfying the issue’s required identity tuple.
- Internal `Protocol` placeholders let the transaction package describe the intended foreign-key seam without creating forbidden imports into sibling branches that are still in flight.
- A dedicated `aeat.domain.financial.transactions` public surface matches the package discipline already established by `aeat.domain.financial.vat` and avoids callers reaching into internal helpers.

## Consequences

- The transaction package deliberately does not solve deduplication, FX normalization, or classification rules; those remain downstream work in later TDP steps.
- The transaction ID algorithm is anchored to the merged T1 shape on `main`, so if upstream `RawTransaction` changes in a future issue, the hash helper will need a deliberate versioned update.
- Catalogue construction from raw mappings remains straightforward for persistence round-trips, but callers that build from iterables should use the package helper so duplicate logical IDs are rejected explicitly.
- The CLI will initially manage a single configured catalogue file under the configured directory; richer multi-catalogue workflows can be layered later without changing the immutable model surface.
