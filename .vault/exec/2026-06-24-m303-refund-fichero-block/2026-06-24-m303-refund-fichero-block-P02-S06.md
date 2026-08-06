---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:0eced201daa89b20cb968cd167fc8b7827f823e5b224e3541afd3d30e25b66f6'
step_id: 'S06'
related:
  - "[[2026-06-24-m303-refund-fichero-block-plan]]"
---

# Add the sepa_marca derivation (1 Espana / 2 UE SEPA / 3 Resto) from the refund-account country

## Scope

- `src/aeat/domain/iva/_refund_eligibility.py`

## Description

- Add the `derive_sepa_marca` function and the `SepaMarca` closed enum classifying the refund account for the DR303 Marca SEPA indicator at DID position 194: `"1"` Cuenta Espana, `"2"` UE SEPA, `"3"` Resto Paises.
- Derive the marca from the account country (the IBAN country code prefix, or the explicit bank country code for a non-SEPA account) and that country's membership of the SEPA zone, rather than storing it as an operator input.
- Ground the SEPA-zone country set in the European Payments Council EPC List of SEPA Scheme Countries (EPC409-09) and Regulation (EU) No 260/2012.

## Outcome

- `derive_sepa_marca` and `SepaMarca` live in `src/aeat/domain/iva/_sepa_marca.py`, exported from the iva package facade, and consumed by the M303 export path.
- The refund golden-SHA cases assert the derived Marca SEPA byte at DID offset 194 is `"1"` for an ES IBAN and the non-SEPA case emits `"3"` with the foreign-bank block. Both pass at HEAD.

## Notes

- The plan Step named `src/aeat/domain/iva/_refund_eligibility.py` as the scope; the implementation instead placed the derivation in a dedicated `_sepa_marca.py` module, a clearer single-responsibility home. This is a scope-file naming deviation only; the functional intent (derive the Marca SEPA from the account country) is satisfied.
- This record documents the verified landed state at HEAD.
