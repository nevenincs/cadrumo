---
generated: true
tags:
  - '#index'
  - '#m303-refund-fichero-block'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:9ab2c4a0d3a08d550227123468811e1f2395768c8ef20168271006b0f9b696ed'
related:
  - '[[2026-06-24-m303-refund-fichero-block-P01-S01]]'
  - '[[2026-06-24-m303-refund-fichero-block-P01-S02]]'
  - '[[2026-06-24-m303-refund-fichero-block-P01-S03]]'
  - '[[2026-06-24-m303-refund-fichero-block-P01-S04]]'
  - '[[2026-06-24-m303-refund-fichero-block-P02-S05]]'
  - '[[2026-06-24-m303-refund-fichero-block-P02-S06]]'
  - '[[2026-06-24-m303-refund-fichero-block-P02-S07]]'
  - '[[2026-06-24-m303-refund-fichero-block-P02-S08]]'
  - '[[2026-06-24-m303-refund-fichero-block-P02-S09]]'
  - '[[2026-06-24-m303-refund-fichero-block-P03-S10]]'
  - '[[2026-06-24-m303-refund-fichero-block-P03-S11]]'
  - '[[2026-06-24-m303-refund-fichero-block-adr]]'
  - '[[2026-06-24-m303-refund-fichero-block-plan]]'
  - '[[2026-07-10-m303-refund-fichero-block-research]]'
---

# `m303-refund-fichero-block` feature index

Auto-generated index of all documents tagged with `#m303-refund-fichero-block`.

## Documents

### adr

- `2026-06-24-m303-refund-fichero-block-adr` - `m303-refund-fichero-block` adr: `REDEME field and IBAN/SWIFT-BIC secure-storage refund block` | (**status:** `accepted`)

### exec

- `2026-06-24-m303-refund-fichero-block-P03-S10` - Extend the golden-SHA fichero roundtrip with a REDEME-1 plus IBAN-populated case, per-offset assertions grounded against the DR303 offsets (110, DID 12, 23, 194)
- `2026-06-24-m303-refund-fichero-block-P03-S11` - Add an end-to-end refusal case asserting a refund disposition with an empty refund-account is refused, not emitted as an empty DID page
- `2026-06-24-m303-refund-fichero-block-P01-S01` - Add the refund-account financial fields (swift_bic, bank_name, bank_address, bank_city, bank_country_code, sepa_marca) to the profile schema as sensitivity financial
- `2026-06-24-m303-refund-fichero-block-P01-S02` - Add the typed refund-account carrier grouping iban and the new fields, with an IBAN structural field validator that rejects a malformed IBAN at the boundary
- `2026-06-24-m303-refund-fichero-block-P01-S03` - Add export_headers redeme to the redeme_enrolled schema field for the page-1 indicator
- `2026-06-24-m303-refund-fichero-block-P01-S04` - Add the secure-storage roundtrip and anti-tautology proof for the new financial refund-account fields
- `2026-06-24-m303-refund-fichero-block-P02-S05` - Emit the REDEME byte mapping redeme_enrolled to 1 or 2 in the header composer
- `2026-06-24-m303-refund-fichero-block-P02-S06` - Add the sepa_marca derivation (1 Espana / 2 UE SEPA / 3 Resto) from the refund-account country
- `2026-06-24-m303-refund-fichero-block-P02-S07` - Read the refund-account block from secure storage transiently and emit the IBAN, SWIFT-BIC, sepa_marca, and per-marca bank sub-fields only on a refund disposition
- `2026-06-24-m303-refund-fichero-block-P02-S08` - Refuse a refund disposition with no refund-account on file with an instructive typed error on the Notice channel, never an empty or partial DID block
- `2026-06-24-m303-refund-fichero-block-P02-S09` - Add the disposition-keyed conditional DID-page emission guard so a non-refund filing emits no empty DID page

### plan

- `2026-06-24-m303-refund-fichero-block-plan` - `m303-refund-fichero-block` plan

### research

- `2026-07-10-m303-refund-fichero-block-research` - m303-refund-fichero-block research: warning closeout research grounding
