---
tags:
  - '#adr'
  - '#m303-refund-fichero-block'
date: '2026-06-24'
modified: '2026-06-24'
related:
  - '[[2026-06-24-m303-refund-election-adr]]'
  - '[[2026-06-21-m303-carry-reconciliation-adr]]'
---

# `m303-refund-fichero-block` adr: `REDEME field and IBAN/SWIFT-BIC secure-storage refund block` | (**status:** `proposed`)

## Problem Statement

The Modelo 303 fichero now sets the declaration type correctly (`D` devolución, via the
part-2 single-fact resolver), but builds a refund filing WITHOUT the two records AEAT
needs to actually pay the refund: the REDEME (Registro de Devolución Mensual) indicator
and the cuenta-devolución block (the IBAN, or SWIFT-BIC plus a foreign bank block for
non-SEPA accounts). The official Diseño de Registros DR303 declares these at fixed
positions — the REDEME indicator at page-1 position 110 (length 1, `"1"` SI / `"2"` NO),
and the refund-account block on the `DP303DID` page (SWIFT-BIC at position 12, IBAN at
position 23, Marca SEPA at position 194). The registry export layout ALREADY declares
every slot at those exact positions, and the fichero serializer is format-generic. Three
gaps remain: the envelope builder never supplies the values; the DID page is emitted
unconditionally (even for a non-refund filing); and the taxpayer profile does not carry
the refund-account data — the profile schema declares `iban` as `sensitivity="financial"`
but the domain model exposes no `iban`/`swift_bic`/bank/`sepa_marca` carrier, and
`redeme_enrolled` has no export-header mapping.

## Considerations

- The IBAN, SWIFT-BIC, and foreign bank block are FINANCIAL IDENTITY DATA. Per the
  sensitive-financial-data invariant they persist ONLY in the encrypted secure-object
  store, are read transiently into memory at export time, and are NEVER written to
  plaintext, logs, or a side store.
- The Diseño slots already exist in the registry export layout at the correct DR303
  positions — no serializer or layout-position change is needed; the work is supplying the
  header values, conditional emission, and the profile carrier.
- The `Marca SEPA` field (0 vacía / 1 Cuenta España / 2 UE SEPA / 3 Resto Países) is
  derived from the IBAN country prefix and SEPA membership — a grounded derivation, not an
  operator input.
- The REDEME byte (`1`/`2`) maps from the standing `redeme_enrolled` profile fact and is
  written on EVERY filing, not only refunds (the Diseño asks for the indicator
  unconditionally).
- The DID refund-account page should be emitted only for a refund disposition (`D`/`X`) —
  the current record-emission guard keys on a positive casilla, which does not express
  "emit when the disposition is a refund".

## Constraints

- Hard invariant: the refund-account financial fields live ONLY in encrypted secure
  storage; the export reads them transiently and never logs them. This gates the schema
  decision (every new field is `sensitivity="financial"`).
- Builds on the landed part-2 single-disposition-fact (`resolve_modelo_result_disposition`)
  — the DID page and the REDEME byte read the same determined fact the declaration-type
  header already uses.
- The golden-SHA fichero roundtrip is the structural authority: any new bytes MUST be
  grounded against the DR303 Diseño offsets (REDEME 110, DID SWIFT 12 / IBAN 23 / SEPA
  194), never hand-tuned to make a hash pass.

## Implementation

- Add the refund-account fields — `swift_bic`, `bank_name`, `bank_address`, `bank_city`,
  `bank_country_code`, `sepa_marca` — to the profile schema as `sensitivity="financial"`
  and a typed carrier (a dedicated refund-account sub-model on the IVA profile is the
  natural home, grouping them with the existing `iban`), so they persist in the encrypted
  secure-object store alongside the existing `iban`. Add `export_headers=["redeme"]` to
  `redeme_enrolled`.
- The envelope builder emits `redeme` (mapping `redeme_enrolled` to `"1"`/`"2"`) on every
  filing; and — only when the determined disposition is a refund — reads the
  refund-account block from the profile's secure storage transiently and emits
  `iban`/`swift_bic`/`sepa_marca`/bank fields. The `sepa_marca` is derived (España / UE
  SEPA / Resto) from the account's country.
- The DID page record gains a refund-disposition emission guard (a new record-level
  conditional keyed on the determined disposition), so a non-refund filing does not emit
  an empty 823-byte DID page where the Diseño intends none.

## Rationale

The official refund record cannot be built from the disposition alone — it needs the
operator's refund account, which is sensitive financial data that must stay encrypted.
Reusing the existing registry slots (already at the correct Diseño positions) and the
part-2 disposition fact keeps the change to supplying values plus conditional emission
plus a secure-storage carrier, rather than re-laying-out the fichero. Deriving
`sepa_marca` rather than asking for it avoids an error-prone operator input. Grounding the
golden-SHA against the published Diseño offsets keeps the byte-level change auditable.

## Consequences

- **Gain:** a devolución fichero carries the REDEME indicator and the refund account AEAT
  pays into — a self-contained, fileable refund artefact.
- **Gain:** the sensitive IBAN/bank data is added under the existing encrypted-secure-storage
  discipline, with a roundtrip plus anti-tautology proof locking the boundary.
- **Difficulty:** new encrypted-profile financial fields (schema + domain carrier +
  secure-storage roundtrip), the `sepa_marca` derivation, and a new disposition-keyed
  record-emission guard; the golden-SHA fixture must be regenerated with a REDEME-1 plus
  IBAN-populated case grounded against the Diseño offsets.
- **Pitfall:** a hand-tuned golden SHA, or any IBAN value reaching a log / plaintext side
  store — the secure-storage roundtrip plus the Diseño-grounded per-offset assertions guard
  both.

## Codification candidates

- **Rule slug:** `fichero-refund-account-is-secure-storage-only`.
  **Rule:** The Modelo 303 (and any modelo) cuenta-devolución refund-account fields (IBAN,
  SWIFT-BIC, bank block) MUST persist only in the encrypted secure-object store as
  `sensitivity="financial"`, be read transiently at export, and never be logged or written
  to a plaintext side store; the fichero refund record is populated from that secure source
  only for a refund disposition.
