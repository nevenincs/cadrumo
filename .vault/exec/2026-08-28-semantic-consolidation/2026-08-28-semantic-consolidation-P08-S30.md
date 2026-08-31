---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:0c4df43ea30db902e3259cc40a506beb16e7c6bed6b5b8722978dc74435e4120'
step_id: 'S30'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Rule on the six tax-id fields that pin a length while matching neither the checksum-validating nor the normalising canonical alias

## Scope

- `src/cadrumo/domain/calculations/registry/`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/gasto193_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/withholding296_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/withholding_bindings.py`
- `verify:` probed bare-9-width against token-plus-9-width on five inputs
- `verify:` `pytest registry -k "withholding or gasto193 or 296" -n 0 -m ""` -> pass (74)
- `verify:` `validate_registry()` -> passes over the whole tree

## Notes

Six fields pinned exactly `min_length=9, max_length=9` -- the Spanish identifier
width -- with neither canonical, and in three cases the canonical sits one line
above in the SAME class. `withholding296_bindings.py` declares
`perceptor_tax_id: TaxIdIdentityToken` and then `representative_tax_id: str |
None = Field(min_length=9, max_length=9)` directly beneath it.

The ruling is the NORMALISING canonical plus the existing width, not the
checksum-validating one, and the probe is why. Against the bare bound:

| input | bare 9-width | token + 9-width |
| --- | --- | --- |
| `12345678z` | stored lowercase | folded to `12345678Z` |
| `" 12345678Z "` | REFUSED (padding makes it 11) | normalised, accepted |
| `1234567Z` | refused | refused |
| `AB123456C` | accepted | accepted |

Strictly better on every column and no new refusal. The lowercase row is the one
that mattered: an unfolded token is what `tax_id_identity_token`'s own docstring
warns about, where two canonically-equal identifiers become two rollups but one
stored row.

The CHECKSUM question is deliberately left open rather than settled here. Moving
these to `SubjectTaxId` would add a refusal to registry-declared AEAT data on my
reading that a legal representative or prior payer is always Spanish-resident,
and one of the six contradicts that in its own docstring -- `nif_pagador_anterior`
says it is obligatory "except where the previous payer is foreign without a
Spanish NIF". That is a tax review, and this campaign has already been bitten
once by arithmetic done in my head rather than grounded.

`nif_pais_residencia` on Modelo 296 is the opposite case and had NEITHER
canonical. It is literally the perceptor's identifier in their own country, on an
IRNR withholding modelo, so it must never take the checksum alias -- no Spanish
control character can validate it. It now takes the normalising token, with the
reason recorded at the field so nobody later "completes" the consolidation by
giving it the checksum.
