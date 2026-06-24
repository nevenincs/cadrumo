---
tags:
  - '#plan'
  - '#m303-refund-fichero-block'
date: '2026-06-24'
modified: '2026-06-24'
tier: L2
related:
  - "[[2026-06-24-m303-refund-fichero-block-adr]]"
---

# `m303-refund-fichero-block` plan

Add the Modelo 303 REDEME indicator and the encrypted IBAN/SWIFT-BIC cuenta-devolucion refund block to the fichero.

## Description

Implements the accepted ADR. The Modelo 303 fichero sets the declaration type (`D`
devolucion) correctly via the part-2 disposition fact, but builds a refund filing without
the REDEME indicator and the cuenta-devolucion block AEAT pays into. The Diseno export
layout already declares every slot at the correct DR303 positions (REDEME at 110; the DID
page SWIFT-BIC at 12, IBAN at 23, Marca-SEPA at 194), and the serializer is format
generic. The work is: carry the refund-account data on the profile in ENCRYPTED secure
storage only (IBAN/SWIFT/bank are sensitivity financial, read transiently at export, never
logged); supply the REDEME byte on every filing and the refund block only on a refund
disposition; derive `sepa_marca` from the account country and emit the per-marca DID
sub-fields; refuse a refund disposition that has no refund-account on file rather than
emit an empty DID block (a fichero AEAT cannot pay); and verify with a Diseno-grounded
golden-SHA roundtrip plus a secure-storage roundtrip and anti-tautology proof.

## Steps

### Phase `P01` - Secure-storage refund-account schema and model

Carry the refund-account fields on the profile in encrypted secure storage with an IBAN validator.

- [ ] `P01.S01` - Add the refund-account financial fields (swift_bic, bank_name, bank_address, bank_city, bank_country_code, sepa_marca) to the profile schema as sensitivity financial; `src/aeat/_data/registry/aeat/user_profile/schema.toml`.
- [ ] `P01.S02` - Add the typed refund-account carrier grouping iban and the new fields, with an IBAN structural field validator that rejects a malformed IBAN at the boundary; `src/aeat/domain/deadlines/_models.py`.
- [ ] `P01.S03` - Add export_headers redeme to the redeme_enrolled schema field for the page-1 indicator; `src/aeat/_data/registry/aeat/user_profile/schema.toml`.
- [ ] `P01.S04` - Add the secure-storage roundtrip and anti-tautology proof for the new financial refund-account fields; `src/aeat/domain/user_profile/tests`.

### Phase `P02` - Fichero envelope wiring and conditional emission

Supply the REDEME byte and the refund block from secure storage, derive sepa_marca, refuse a no-account refund.

- [ ] `P02.S05` - Emit the REDEME byte mapping redeme_enrolled to 1 or 2 in the header composer; `src/aeat/application/modelo/_export.py`.
- [ ] `P02.S06` - Add the sepa_marca derivation (1 Espana / 2 UE SEPA / 3 Resto) from the refund-account country; `src/aeat/domain/iva/_refund_eligibility.py`.
- [ ] `P02.S07` - Read the refund-account block from secure storage transiently and emit the IBAN, SWIFT-BIC, sepa_marca, and per-marca bank sub-fields only on a refund disposition; `src/aeat/application/modelo/_export.py`.
- [ ] `P02.S08` - Refuse a refund disposition with no refund-account on file with an instructive typed error on the Notice channel, never an empty or partial DID block; `src/aeat/application/modelo/_export.py`.
- [ ] `P02.S09` - Add the disposition-keyed conditional DID-page emission guard so a non-refund filing emits no empty DID page; `src/aeat/application/filing/_export.py`.

### Phase `P03` - Verification

Golden-SHA roundtrip, secure-storage roundtrip, and the no-account refusal case.

- [ ] `P03.S10` - Extend the golden-SHA fichero roundtrip with a REDEME-1 plus IBAN-populated case, per-offset assertions grounded against the DR303 offsets (110, DID 12, 23, 194); `src/aeat/adapters/outbound/aeat/export/_formats/tests/test_fichero_boe_roundtrip.py`.
- [ ] `P03.S11` - Add an end-to-end refusal case asserting a refund disposition with an empty refund-account is refused, not emitted as an empty DID page; `src/aeat/application/modelo/tests`.

## Parallelization

P01 lands before P02 - the envelope reads the secure-storage carrier P01 adds. Within P01, S01 then S02 then S03 are sequential (schema, then the typed carrier, then the redeme header mapping); S04 follows S02. The P02 steps S05 through S09 all touch `_export.py` or the shared export layout, so they are sequenced rather than parallel. P03 verification follows P02; S10 (golden-SHA) and S11 (refusal e2e) are independent and may run in parallel.

## Verification

- The secure-storage roundtrip plus anti-tautology proof pass: every new refund-account financial field survives the real encrypted save and load cycle, and a corrupted-on-disk field is refused or surfaces strict inequality.
- The golden-SHA fichero roundtrip passes with the REDEME-1 plus IBAN-populated case, with per-offset assertions naming DR303 rows 110 and DID 12 / 23 / 194, the SHA regenerated from the real serialiser (never hand-tuned).
- The no-account refusal case: a refund disposition with no refund-account on file is refused with the instructive typed error, never an empty DID page.
- Registry loads; locales scaffold --check clean; ruff and ty clean on changed files; the documented-command conformance gate green; no IBAN value reaches a log or plaintext side store.
