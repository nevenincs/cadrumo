---
tags:
  - '#adr'
  - '#ledger-interface-contract'
date: '2026-06-10'
related:
  - "[[2026-06-10-ledger-interface-contract-research]]"
---



# `ledger-interface-contract` adr: `Uniform ledger response envelope, ID resolution, and sorting` | (**status:** `accepted`)

## Problem Statement

The `aeat app ledger` CLI exposes 26 verbs whose successful `--json` responses
already share a uniform outer envelope (`{schema_version, command, result,
warnings}`), but whose inner `result` payloads diverge in ways that break the
"uniform CRUD contract" an operator and a pipeline consumer should be able to
rely on. The research finds three concrete classes of divergence: (1) the
single-transaction mutation payloads are inconsistent — `add` is missing the
`review_status` field every other mutation carries, `link` returns no
`transaction` projection of the object it just mutated, and `classify` is an
all-optional union that cannot be discriminated; (2) several read/list payloads
expose bare `list[dict[str, object]]` wire boundaries that violate
`aeat-architecture-boundaries`; (3) there is no way to address a single
transaction by a uniform id-input convention (mutation verbs use `--id`, read
verbs use a positional argument, classify/review make it optional), the
CLI-facing id-resolution shim is duplicated, and the `ledger list` read surface
has no sort capability at all. This ADR settles one canonical contract for the
envelope payloads, the id-input convention, and the sort surface, so the
cluster's later plan executes against a single decision rather than relitigating
each verb.

This is a factory-campaign cluster (C5) on the unreleased pre-beta branch, so
every change is a clean break: no migration of an older payload shape, no
deprecated alias kept alive (`no-legacy-compatibility`).

## Considerations

- **The envelope is not the problem.** The shared `_emit_envelope` /
  `SchemaEnvelope` wrapper is correct and pinned by the
  `2026-06-01-envelope-conformance-gate` and
  `2026-06-02-emit-envelope-schema-burndown` gates. This ADR changes only the
  per-verb `result` payloads declared in `_ledger_payloads.py`, never the outer
  envelope contract.

- **Money shape is fixed by C1.** Transaction amounts are non-negative magnitude
  plus a `direction`. Every typed row/envelope shape this ADR defines carries a
  non-negative `amount` string and a `direction` field; the existing
  `TransactionPayload` already honours this and is reused, not re-derived.

- **The list function is shared with C6.** `project_ledger_list` is the single
  injection point for both the C6 filter and this ADR's sort. Sort must be
  applied after the filter and after `--group` selection, and the sort params
  must compose with the filter params on the same function signature.

- **The participation read verb (C7) rides this envelope.** The C7 transaction
  participation read surfaces through the same uniform contract; this ADR
  reserves a typed `LedgerTransactionParticipationPayload` slot for it so C7
  does not introduce a parallel bare-dict shape.

- **Honest temporal sort needs a real timestamp.** A `--sort-by created_at` is
  only honest if every row has a creation timestamp. Today `Transaction` has
  none; only imported rows carry `raw.provenance.ingested_at`.

## Constraints

- **Cross-cluster coupling on `project_ledger_list`.** This ADR's sort and C6's
  filter both mutate the same function. The two clusters must coordinate the
  final signature so neither overwrites the other; the plan step that lands sort
  must rebase onto C6's filter params (or land jointly).

- **`Transaction` is a roundtrip-bound persisted record.** Adding `created_at` /
  `modified_at` to `Transaction` touches the encrypted-bucket persistence
  boundary; the change requires a strict save→load→equality roundtrip test with
  the new fields populated non-default (`aeat-roundtrip-discipline`), and the
  fields ride the same `transaction-catalogue:{bucket_id}` encrypted object.

- **No external numeric oracle is involved.** These are structure / wiring /
  provenance contracts, so the tests assert schema shape, envelope conformance,
  sort stability, and roundtrip identity — not hand-computed Decimals
  (`no-tautological-calculation-tests`).

- **The 26-verb roster is pinned.** `test_ledger_verb_spine.py` and the
  `register_schema` registry gate any roster change; this ADR adds no verb and
  removes none, so those gates stay green by construction.

## Implementation

The implementation is a payload-contract normalisation plus two additive
capabilities (uniform id input, list sort), settled here as seven decisions.

**D1 — Uniform single-transaction mutation envelope.** Every verb that mutates
exactly one transaction returns the quintet `{bucket_id, transaction_id,
bucket_event_ids, review_status, transaction: TransactionPayload}` — the
existing `_LedgerMutationResult` shape. Concretely: `LedgerAddResult` is changed
to subclass `_LedgerMutationResult` so it gains `review_status`; `LedgerLinkResult`
gains a `transaction: TransactionPayload` slot (and its `evidence_update`
bare-dict is replaced with a typed payload, per D2); the single-transaction
branch of `LedgerClassifyResult` is normalised so its mutation quintet is the
primary, non-optional shape and the bulk / llm / saturate branches are
discriminated rather than flattened into one all-optional class. The structural
verbs keep their distinct shapes: `split` (parent + children + group id),
`merge` (merged id + source children), `remove` / `reset` (cascade lists +
`blocking_modelo_references`). These act on a set or destroy the subject, so a
single `transaction` slot does not apply; the ADR defines them as the
deliberate exceptions to the mutation quintet.

**D2 — Typed row/list payloads replace every `list[dict[str, object]]`.** Each
bare-dict wire boundary becomes a strict `OutputSchema`. The list-row schema
(`LedgerListRowPayload`) carries `full_id`, `display_id`, `date`, non-negative
`amount` + `direction`, `description`, `review_status`, `lifecycle_state`,
`business_classification`, `group_label`, and the new `created_at` / `modified_at`
(D6). It is projected from the existing `LedgerTransactionReviewPayload` plus the
three id/group keys the list builder already appends, so the source projection is
reused. The same typed-schema treatment applies to `history` events, `track`
tracking, the import transaction-refs, export rows, and the business-invoice /
inventory / evidence list rows.

**D3 — One shared id-resolution shim.** The two duplicate `_resolve_id` CLI
shims collapse into one shared helper (a single CLI-boundary wrapper over the
canonical `resolve_transaction_id`), with the lineage-following read variant
(`_resolve_read_id` → `resolve_lineage_transaction_id`) kept as the distinct
read-side path. The application-layer resolvers are unchanged — they are sound.

**D4 — Uniform id-input convention: positional `Argument`.** Every verb that
addresses a single transaction — read **and** mutation — takes the id as a
positional Typer `Argument`, not a `--id` Option. Positional is the common CLI
idiom for "the subject of the command" and it is already what the read verbs
use, so this converges on the smaller migration surface. `classify` / `review`,
which today make the id optional, take an optional positional consistent with
their dual single/bulk nature. As a clean break, the `--id` Option is removed
outright from the mutation verbs (`no-legacy-compatibility`); no alias is kept.

**D5 — List sort.** `project_ledger_list` gains `--sort-by` and `--sort-order`,
applied after the C6 filter and `--group` selection and before paging.
`--sort-by` accepts a closed enum (`date`, `value_date`, `amount`, `description`,
`created_at`, `modified_at`, `classified_at`, `lifecycle_state`,
`classification`); the enum is declared in `core/` so the Typer boundary renders
the accepted-value `Choice([...])` (`aeat-architecture-boundaries`).
`--sort-order` is `asc` | `desc`. The sort is **stable** with a deterministic
final tie-break on the content-addressed `transaction_id`, so equal-key rows
have a fixed order across runs (replacing today's meaningless hash-keyed
`--by-group` secondary).

**D6 — Add `created_at` / `modified_at` to `Transaction`.** Because the project
is pre-beta with no released data, the honest fix is to add `created_at` and
`modified_at` as clean-break fields on the `Transaction` persistence record
(set at `ledger add` and stamped on every mutating edit), rather than deriving a
partial timestamp from `ingested_at` (which exists only for imported rows). This
makes `--sort-by created_at|modified_at` honest for every row. The fields ride
the encrypted bucket catalogue and are covered by a strict
save→load→equality roundtrip test with both populated non-default.

**D7 — Pipeable JSON.** Every verb's `--format json` emits the uniform
`SchemaEnvelope`, so output composes into further operations. This is already
true via `_emit_envelope`; the ADR pins it as a contract so the typed-payload
normalisation above does not regress any verb to a non-enveloped emit.

## Rationale

The research (`2026-06-10-ledger-interface-contract-research`) establishes that
the outer envelope is already uniform and the divergence is confined to the
`result` payloads, so the cheapest high-leverage fix is to normalise those
payloads rather than redesign the response system. Reusing the existing
`TransactionPayload` and `LedgerTransactionReviewPayload` projections (finding C)
means the typed-row work is mostly re-typing an existing flattening site, not
new projection logic. Choosing the positional `Argument` convention (D4)
converges on the convention the read verbs already use, minimising churn, and
the `no-legacy-compatibility` rule makes the outright removal of `--id` the
correct clean-break action on an unreleased branch. Adding real `created_at` /
`modified_at` (D6) rather than deriving from `ingested_at` is the only way a
temporal sort can be honest for manually-added rows, and the pre-beta status
removes any migration cost — there is no older record shape to upgrade. The
secure-storage gate (research finding G) confirms the entire contract change is
projection-and-input shaping over the encrypted bucket; no list/export path
writes plaintext, so the change carries no new persistence-leak surface beyond
the D6 field addition, which is covered by the mandated roundtrip test.

## Consequences

- **Gain:** a pipeline consumer can rely on one mutation-response shape across
  `add`/`update`/`classify-single`/`allocate`/`attach`/`doclink`/`archive`/
  `stash`/`restore`/`link`, every list row is a typed schema, the id input is
  one convention, and the list is sortable on honest fields. The all-optional
  `classify` union stops being undiscriminable.

- **Difficulty:** D4 (positional id) and the `--id` removal are operator-facing
  breaking changes; every doc, help string, and conformance test that names
  `--id` must be updated in the same atomic change. D5/D6 couple to C6's filter
  on `project_ledger_list`, so the sort step must coordinate or co-land with the
  C6 filter step to avoid signature churn.

- **Pitfall:** D6 adds fields to a roundtrip-bound persisted record; a
  save-drops-field regression is invisible unless the roundtrip fixture
  populates both timestamps non-default, so the roundtrip test is mandatory, not
  optional. `modified_at` semantics must be defined precisely (which edits stamp
  it — every mutating verb, or only field edits) or the sort becomes
  inconsistent.

- **Pathway opened:** once every mutation returns the uniform typed quintet and
  every list row is typed, the C7 participation read verb slots into the same
  contract via its reserved `LedgerTransactionParticipationPayload`, and a future
  general `aeat app` response-shape conformance gate can assert the mutation
  quintet across domains beyond ledger.

## Codification candidates

- **Rule slug:** `ledger-mutation-returns-uniform-quintet`.
  **Rule:** Every CLI verb that mutates exactly one ledger transaction must
  return the `{bucket_id, transaction_id, bucket_event_ids, review_status,
  transaction: TransactionPayload}` quintet through the shared
  `_LedgerMutationResult` shape; structural verbs (split/merge/remove/reset)
  that act on a set or destroy the subject are the only exceptions and must
  declare their own typed shape.

- **Rule slug:** `cli-single-subject-id-is-positional`.
  **Rule:** A CLI verb that addresses one ledger transaction must accept the id
  as a positional `Argument` resolved through the single shared shim over
  `resolve_transaction_id`, never as a `--id` Option and never via a duplicated
  resolver.


