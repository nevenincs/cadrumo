---
tags:
  - '#adr'
  - '#identity'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-identity-research]]"
---
# `identity` adr: `core/identity placement: tax-ID validation as a security primitive` | (**status:** `accepted`)

## Problem Statement

Spanish tax-identifier validation (NIF / NIE / CIF) is a cross-cutting
primitive consumed by at least four call sites in the codebase:

- the invoice domain validator for counterparty tax-ids
- the unsecured-master-key NIF canary, which refuses to encrypt under
  the in-memory fallback provider when a real taxpayer NIF is present
- the inbound-PDF sanitizer's record validator
- the inbound-adapter identity re-export

Before the restructure the algorithm lived inline in
`adapters/outbound/aeat/auth/...`, where it could not be reused by
the persistence or sanitizer layers without crossing layer
boundaries. The restructure relocated the algorithm but no `.vault/`
trail recorded the placement decision — flagged by audit #506 (HIGH)
as a security-relevant primitive lacking an ADR.

## Considerations

The algorithm itself is the Agencia Tributaria's published mod-23
checksum: NIF is 8 digits followed by the lookup letter from
`"TRWAGMYFPDXBNJZSQVHLCKE"` indexed by `number % 23`; NIE substitutes
the leading X/Y/Z with 0/1/2 before applying the NIF rule; CIF is a
leading letter from `"ABCDEFGHJKLMNPQRSUVW"` plus 7 digits plus a
1-character control whose form (digit vs letter) depends on the
leader. This contract is fixed by AEAT and cannot diverge.

Placement options considered:

1. Keep the algorithm inside `adapters/outbound/aeat/auth/`. Forces
   every other consumer to either reach across the layer boundary
   (an import-linter violation) or maintain its own copy of the
   algorithm — guarantees algorithmic drift.

2. Place under `domain/` (e.g. `domain/identity/`). Workable, but the
   project reserves `domain/` for tax-domain business records (the
   filing, calculation, deadline, transaction, invoice domains) and
   the identity primitive is shared infrastructure, not a domain
   record itself.

3. Place under `core/` as a domain-agnostic primitive. Matches the
   established `core/` layer convention (utility primitives consumed
   by adapters/domain/application alike — `core/locks`, `core/logging`,
   `core/file_permissions`, etc.).

## Constraints

- **Layer-boundary discipline**: `core/` is allowed to be imported by
  every other layer; the inverse direction is not. Placement in
  `core/` keeps consumers' imports legal under the project's
  import-linter contracts.

- **Pure-function discipline**: the algorithm has no I/O, no network,
  no filesystem, no global state. It must be cheap enough to call on
  every invoice / every sanitizer record / every CLI preflight gate
  without observable overhead.

- **Stable public-API surface**: existing consumers depend on the
  function name `validate_spanish_tax_id`, its single positional
  `value: str` argument, its canonical-string return shape, and its
  `IdentityError`-on-failure raise contract. The ADR must not change
  these.

## Implementation

The implementation lives in `src/aeat/core/identity/`:

- `_tax_id.py` — the `validate_spanish_tax_id(value)` function and
  the three private helpers `_validate_nif`, `_validate_nie`,
  `_validate_cif`. The CIF helper carries the digit-vs-letter
  control dispatch based on the leader's membership in
  `_CIF_LETTER_CONTROL_LEADERS = set("KPQRSNW")` (always-letter)
  versus the broader `_CIF_LEADERS = "ABCDEFGHJKLMNPQRSUVW"`.

- `_documents.py` — the `IdentityDocument` `StrEnum` (the three
  document kinds), the `IdentityError` typed-failure shape, and the
  `validate_identity` surface that returns the matching enum member
  rather than the canonical string. Used by callers that need to
  branch on document kind.

- `__init__.py` — re-exports `IdentityDocument`, `IdentityError`,
  `validate_identity`, `validate_spanish_tax_id` as the public
  surface.

The inbound-adapter `adapters/inbound/identity/` is a thin
re-export of `validate_spanish_tax_id` only. This pattern lets
inbound-side adapters (PDF parsers, XLSX readers, external-service
clients) call a layer-local symbol instead of importing across the
layer boundary into `core/`. The re-export carries no
implementation — it forwards directly to the `core` symbol.

## Rationale

`core/` is the right home because:

1. The algorithm is shared between adapters (master-key NIF canary,
   sanitizer, inbound identity, outbound auth) and domain (invoice
   counterparty validator). No other layer satisfies "importable by
   every consumer without violating layer-boundary discipline".

2. The algorithm is stable AEAT-published infrastructure with no
   business-logic content; placing it under `domain/` would muddy
   the `domain/` invariant ("tax-domain business records, not
   shared primitives").

3. The function returns the canonical uppercased+stripped form
   rather than just a boolean. Callers that need only well-formedness
   (the master-key NIF canary, the CLI preflight gates) consume the
   string; callers that need to branch on document kind (the
   sanitizer record validator) consume `validate_identity` which
   returns the enum.

4. The `adapters/inbound/identity/` re-export pattern keeps inbound
   adapters' imports layer-local without duplicating algorithm code.

## Consequences

- **Public-API contract is now load-bearing across four call sites.**
  Renaming `validate_spanish_tax_id`, changing its raise contract
  from `IdentityError` to a different exception, or returning a non-
  canonical form would break the master-key NIF canary's
  unsecured-storage refusal — a security regression. The function
  name and shape are part of the project's stability surface.

- **Test coverage is concentrated in `domain/invoices/test_validators.py`.**
  Fourteen tests pin the NIF / NIE / CIF algorithm against
  AEAT-known fixtures and the separator / ES-VAT-prefix normalisation
  rules. The identity module itself has no dedicated `test_tax_id`
  file because the invoice validator's coverage is exhaustive.

- **Future consumers should import from `aeat.core.identity` or
  `aeat.adapters.inbound.identity`** depending on their layer.
  Adapter-layer code that needs the validator must NOT reach across
  the boundary into `aeat.core.identity` directly — go through the
  inbound-adapter re-export.

- **The `_SYNTHETIC_TAX_IDS` allow-list lives in the master-key
  module, not here.** The identity validator is purely an algorithm
  check; the "this is a placeholder / canary value" predicate is
  a persistence-layer concern. The current
  `refuse_unsecured_with_real_nif` flow chains `validate_spanish_tax_id`
  with the synthetic-NIF check inside `master_key._master_key`,
  preserving the layered separation.

- **The CIF historical-form tolerance is intentional.** Real CIFs in
  circulation use both digit and letter controls depending on the
  registration era. The validator accepts both forms for the broader
  `_CIF_LEADERS` set, restricting to letter-only for the
  `_CIF_LETTER_CONTROL_LEADERS` subset. Refusing the digit form for
  the broader set would reject legitimate historical NIFs.
