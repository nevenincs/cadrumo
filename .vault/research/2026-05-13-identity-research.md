---
tags:
  - '#research'
  - '#identity'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-identity-adr]]"
---



# `identity` research: `Spanish tax-ID validation: algorithm + cross-package consumers`

Backfill captured to satisfy the first acceptance criterion of audit
gap #506 — the identity domain ships in production with no `.vault/`
research trail. This document captures the Agencia Tributaria-published
mod-23 / Luhn-style algorithm, the four cross-package consumer call
sites, the existing test fixture set, and the rationale for the CIF
historical-form tolerance baked into the validator.

## Findings

### Algorithm reference

Spanish tax identifiers come in three shapes, all published by the
Agencia Estatal de Administración Tributaria:

**NIF (Número de Identificación Fiscal)** — Spanish-national taxpayer
identifier. Eight numeric digits followed by a one-character check
letter. The check letter is the `(number % 23)`-th entry of the
canonical letter table `TRWAGMYFPDXBNJZSQVHLCKE`. Worked example: NIF
`12345678Z` → 12345678 % 23 = 14 → table[14] = `Z` → valid.

**NIE (Número de Identidad de Extranjero)** — Foreign-resident
identifier. Single leading letter `X` / `Y` / `Z`, then seven digits,
then a one-character check letter. The check letter is computed by
substituting the leading letter with `0` / `1` / `2` respectively
(`X→0`, `Y→1`, `Z→2`) and applying the same `% 23` mod-23 lookup as
NIF. Worked example: NIE `X1234567L` → numeric = `01234567` → 1234567
% 23 = 11 → table[11] = `L` → valid.

**CIF (Código de Identificación Fiscal)** — Legal-entity identifier.
One leading "kind" letter from the closed set
`ABCDEFGHJNPQRSUVW` (each letter encodes a corporate kind:
sociedad anónima, sociedad limitada, asociación, etc.), then seven
digits, then a one-character check that can be a digit `0-9` or a
letter from the table `JABCDEFGHI`. The check value is the AEAT
Luhn-style sum:

- For each odd-position digit (1-indexed), double it; if the doubled
  value is ≥ 10, add its decimal digits (i.e., `divmod(2*digit, 10)`
  componentwise).
- For each even-position digit, add it directly.
- Sum these contributions.
- The check value is `(10 - (sum % 10)) % 10`.

Whether the check is rendered as a digit or as a letter from
`JABCDEFGHI` depends on the leading kind. The validator partitions
the kinds into three groups (see "boundary-case rationale" below).

### Cross-package consumer survey

The identity validator is consumed at four call sites, each
needing a different facet of the contract:

1. **Invoice counterparty validation** — `domain/invoices/_models.py`
   calls `validate_spanish_tax_id(tax_id_raw)` from within the
   `Invoice` pydantic model_validator. Consumes the canonical-string
   return (the validated, uppercased, stripped form is written back
   into `payload["counterparty_tax_id"]`) and propagates the
   `IdentityError` raise to surface invalid invoice imports at
   parse time.

2. **Master-key NIF canary** — the unsecured-master-key fallback in
   `adapters/persistence/storage/master_key/_master_key.py` defines
   `refuse_unsecured_with_real_nif(tax_id, ...)` which chains
   `validate_spanish_tax_id` with a `_SYNTHETIC_TAX_IDS` allow-list
   check. The canonical-string return is what the synthetic-NIF set
   is compared against. This is the most security-sensitive
   consumer — the validator's stability gate ensures that a real
   taxpayer NIF never lands under the unsecured backend, which
   would otherwise put a tax-id at-rest under no encryption.

3. **Sanitizer record validator** — `adapters/inbound/sanitizer/_records.py`
   uses `validate_spanish_tax_id` as the
   `pydantic.field_validator` on `NifReplacement.synthetic`,
   ensuring that any sanitizer-supplied replacement tax-ID is a
   valid NIF/NIE before it is written into a sanitised record.

4. **Inbound-adapter re-export** — `adapters/inbound/identity/__init__.py`
   re-exports `validate_spanish_tax_id` so inbound-side adapters
   (PDF parsers, XLSX readers, external-service clients) can
   validate without importing across the layer boundary into
   `core/`. The re-export forwards directly with no extra
   adaptation.

Of these, only #1 and #3 reach for the `IdentityDocument` enum
indirectly via the matching `validate_identity` surface elsewhere.
Consumer #2 and #4 only need the well-formedness check, so they
consume the canonical-string variant.

### Test-coverage trail

The identity module itself has no dedicated `test_tax_id` file
because `domain/invoices/test_validators.py` carries fourteen
focused fixtures that exhaustively pin the algorithm:

- `test_validate_spanish_tax_id_accepts_known_valid_nif` — sweeps a
  parametrised set of known-valid NIF strings against the algorithm.
- `test_validate_spanish_tax_id_accepts_known_valid_nie` — sweeps
  NIE happy-path values with each X / Y / Z prefix.
- `test_validate_spanish_tax_id_accepts_cif_digit_control` — CIF
  with a leading kind in the digit-only set
  (`ABEH`), expects the digit-form check.
- `test_validate_spanish_tax_id_accepts_cif_letter_control` — CIF
  with a leading kind in the letter-only set (`KPQRSNW`), expects
  the letter-form check from `JABCDEFGHI`.
- `test_validate_spanish_tax_id_accepts_abeh_letter_form` — the
  ABEH leaders are documented as digit-only, but a real subset of
  historical CIFs in circulation carry the letter form for these
  leaders; the validator accepts both, pinned by this test.
- `test_validate_spanish_tax_id_rejects_invalid_checksum` —
  algorithmic-failure path, ensures the validator does not just
  shape-match.
- `test_validate_spanish_tax_id_rejects_malformed_shapes` —
  shape-failure path: wrong length, wrong character set,
  unsupported leader.
- `test_validate_spanish_tax_id_strips_common_separators` — pins
  the `-`, ` `, `.` separator-strip behaviour (real AEAT-emitted
  taxpayer strings come with various separators).
- `test_validate_spanish_tax_id_strips_es_vat_prefix` — pins the
  EU-VAT `ES`-prefix stripping (`ES12345678Z` → `12345678Z`).
- `test_validate_vat_number_*` — sister tests covering the broader
  EU-VAT-number validator, which delegates to country-specific
  shape regexes after stripping the country prefix.
- `test_validate_country_code_*` — pins the ISO 3166-1 alpha-2
  country-code normalisation that the VAT validator depends on.

This concentration of coverage in the invoice-domain test module
reflects the invoice domain being the most-frequent consumer
(every invoice import path runs the validator). A future
`test_identity.py` in `core/identity/` could relocate the algorithm
tests for discoverability, but the contract is identical and the
existing fixtures already verify every branch.

### Boundary-case rationale: CIF historical-form tolerance

The CIF validator partitions the leading-kind letters into three
sets, derived from AEAT's published spec:

- `_CIF_KIND_DIGIT_ONLY = "ABEH"` — kinds whose check character is
  strictly a digit per the AEAT publication. Refusing the letter
  form would reject some historical CIFs in circulation; the
  validator therefore ALSO accepts the letter form for these kinds.
- `_CIF_KIND_LETTER_ONLY = "KPQRSNW"` — kinds whose check character
  is strictly a letter from `JABCDEFGHI`. The digit form is
  rejected.
- Everything else in `_CIF_KIND_LETTERS = "ABCDEFGHJNPQRSUVW"`
  (i.e., `CDFGJUV`) is documented as "either form" — the validator
  accepts both digit and letter form.

The "ABEH historical-letter-form tolerance" exists because real
CIFs registered in earlier eras of the AEAT system carry the
letter check on what is now documented as digit-only. Strictly
rejecting them would break invoice imports for legitimate Spanish
companies. The validator's behaviour matches AEAT's own online
validator's behaviour (a CIF with the historical letter form on
an ABEH leader is accepted on the public consulta surface), so
the looseness is not a security regression — it tracks AEAT's
actual canonical-acceptance contract.

### Canonical-form return shape

`validate_spanish_tax_id` returns the validated input stripped of
separators (`-`, ` `, `.`) and uppercased. This is the form that
the master-key NIF canary's `_SYNTHETIC_TAX_IDS` set is compared
against, the form that the invoice model writes back to its
`counterparty_tax_id` field, and the form that the sanitizer
`NifReplacement.synthetic` field stores. Changing this shape (for
example, returning the lowercased form, or returning the raw
input on success) would silently break the canary, the invoice
model, and the sanitizer in different ways. The canonical-form
return is part of the stable public-API contract documented in
the matching ADR.

### Open questions / future work

- **Dedicated `test_identity.py`** under `core/identity/`. The
  current coverage lives in `domain/invoices/test_validators.py`
  for historical reasons (the validator was first consumed by the
  invoice domain). A relocated test module would improve
  discoverability without changing coverage.
- **EU-VAT cross-validator unification**. The companion
  `validate_vat_number` and `validate_country_code` helpers live
  in the same invoice-validators module — they could be promoted
  to `core/identity` alongside `validate_spanish_tax_id` so EU-VAT
  callers do not reach across the layer boundary either. Out of
  scope for this audit-gap backfill.
