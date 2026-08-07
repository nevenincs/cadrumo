---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:7a2d126c19fa3cc9c34788bac9acb63829109f09f76e2780c2767d3e4e6a369b'
step_id: 'S12'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Record the lane-partition decision explicitly, whether the slim store's per-source-kind document partition is reproduced on the canonical home or consciously dropped in favour of the existing per-consumer gates, naming those gates and what each still guarantees

## Scope

- `src/cadrumo/domain/invoices/_service.py`

## Description

- Established what the slim store's physical partition actually guaranteed, rather than what it appears to guarantee.
- Enumerated the per-consumer gates that survive it, naming what each still guarantees.
- Recorded the decision and the one guarantee that is genuinely not reproduced.

## Outcome

**Decision: the per-source-kind document partition is CONSCIOUSLY DROPPED, not reproduced.** The bucket partition is kept; the direction partition is not.

The slim store keys its document on `(bucket_id, source_kind)`, so payable and collectible records live in physically separate encrypted documents. The canonical store is one document per profile, with direction carried as a typed field on each record.

**What the physical partition actually guaranteed — and what it did not.** It guaranteed that loading one lane did not deserialise the other, and that a lane read could not return a record of the other direction. It did NOT guarantee correctness of direction: nothing stopped a record being written into the wrong lane's document, and had that happened the partition would have made the error harder to see, not easier, because the record's own direction field and its storage location could disagree with no reconciliation between them.

The canonical store cannot have that disagreement: there is one place a record can be, and its direction is a property of the record rather than of where it sits.

### The per-consumer gates that survive, and what each guarantees

| Gate | What it still guarantees |
|---|---|
| `invoice_direction_to_source_kind` | The single contractual direction-to-settlement mapping. Issued settles collectible, received settles payable, for every consumer. Proven total over the direction enum by an existing anti-tautology test. |
| `_invoice_source_kind` + `_invoice_sources_for_revision` | A record only feeds bindings whose declared source matches its own direction. This is what the physical lane split did at read time, now done per record instead of per document. |
| `_COLLECTIBLE_M349_OPERATION_TYPES` / `_PAYABLE_M349_OPERATION_TYPES` | A clave that is impossible on a record's direction is refused. This is STRONGER than the partition ever was: it checks the direction against the operation's meaning, where the partition only checked which file the record came out of. |
| `_assert_catalogue_bucket` | Bucket isolation, on both read and write. The partition axis that actually protects one taxpayer from another is retained in full. |
| The decomposition self-contradiction check | A record whose declared treatment contradicts its own figures is disqualified from M349. Unrelated to direction, and unaffected. |

### The one guarantee genuinely not reproduced

**Loading one direction no longer avoids deserialising the other.** A bucket's whole invoice catalogue is loaded, then filtered per record. That is a performance and blast-radius property, not a correctness one: a decryption failure now affects the whole catalogue rather than one lane of it.

Recorded rather than waved past, because it is a real change and the reason it is acceptable is specific: the canonical store already had this shape before this campaign, the resolver already loaded it whole, and the failure mode it introduces — a corrupt catalogue degrading both lanes — is already handled by the storage-degradation path the resolver runs, which surfaces a typed degradation resolution rather than a silent empty result.

## Verification

Closed by an artefact rather than by a green assertion, per this Step's own criterion. The claims were measured at `HEAD`:

    _business_operation_invoice.py:391,447   document key is (bucket_id, source_kind)
    _source_resolver.py:148,165,391          per-record direction filtering on the canonical path
    _source_resolver.py:88,100               direction-specific M349 clave sets
    adapters/persistence/profile/invoices.py bucket-ownership guard on read and write

Each gate named above is exercised by existing tests in the resolver and persistence suites; this Step adds no new gate, because the decision is to rely on gates that already exist rather than to rebuild the partition.

## Notes

The ADR forbids dropping a structural guarantee by oversight, which is why the one genuinely-lost property is stated plainly rather than absorbed into the table of surviving gates. Dropping it by decision is permitted; dropping it without noticing is not, and the difference is only visible if the record says which happened.

The direction partition was, on inspection, the weaker of the two axes the slim store split on. Bucket isolation protects one taxpayer's data from another's and is retained in full; direction separation protected a record from being read under the wrong source kind, which a typed field on the record does more directly and with no possibility of the location and the field disagreeing.
