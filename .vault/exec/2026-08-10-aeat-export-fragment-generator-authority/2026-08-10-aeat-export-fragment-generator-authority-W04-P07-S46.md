---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:d0595dccda293e8e4f6b9e2ef09128aaa1c03cd787255ba4b1074ba6b503a914'
step_id: 'S46'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Land the typed canonical producer substrate and public producer snapshot for M303: a dedicated `PresenterIdentity`, stable taxpayer/model profile facts (including M111, M202, and M303), immutable filing elections with amendment evidence, and the disposition-selected secure refund/charge-account projection. Delete duplicate producer owners and plaintext financial-data persistence, and prove the snapshot is complete, typed, immutable, and fail-closed. This step ends at the producer substrate/snapshot boundary: it does not define registry semantic vocabulary or axes, edit semantic-map schema, migrate registry maps or renderers, migrate raw export headers, or change the generator/composer integration, and those are S45's subsequent integration work

## Scope

- `src/cadrumo/domain/deadlines/`
- `src/cadrumo/application/user_profile/`
- `src/cadrumo/application/modelo/`
- `src/cadrumo/application/filing/`

## Description

- Add one strict frozen public filing producer snapshot with a separately required presenter identity, immutable filing elections, typed amendment evidence, and disposition-selected account projection.
- Reuse `TaxpayerProfile` as the canonical M202 stable-fact owner and `ModeloIVAProfile` as the canonical M303 profile owner instead of redeclaring their fields.
- Retain repeatable M202 CNAE facts without inventing a greatest-turnover selector, and enumerate the unsupported principal CNAE plus official offsets 122 through 132 and 147 exactly.
- Refuse incomplete M111 `colegio_concertado`, unsupported M202 snapshots, model/profile mismatches, contradictory domiciliaciÃ³n elections, missing required accounts, embedded unselected accounts, malformed amendment evidence, and unsupported modelos.
- Generate and verify the required API documentation scaffold and expose the substrate through the filing facade.

## Outcome

The public producer boundary is typed, immutable, and fail-closed without defining any registry semantic vocabulary or changing the S45-owned renderer, semantic maps, raw export headers, or composer integration. Presenter identity has no taxpayer fallback. Amendment kind is the sole stored flag authority, and the original AEAT receipt is exactly thirteen digits.

M202 references the canonical `TaxpayerProfile`; its repeatable CNAE facts do not claim a principal activity, and every unadmitted producer remains in the exact immutable unsupported inventory. M303 directly uses the canonical `ModeloIVAProfile`. The builder removes embedded account fields from those canonical profiles and retains only a charge or refund selection justified by the resolved disposition; a direct snapshot construction with embedded accounts or a mismatched role refuses.

Focused verification passed 12 tests. Scoped Ruff passed. Scoped strict BasedPyright reported zero errors, warnings, and notes. API scaffold conformance and cached diff checks passed. Independent Luna review first found the M202 and M303 duplicate profile classes as a high-severity canonical-home violation; those classes and exports were deleted, canonical owners were composed directly, and re-review passed with zero critical, high, medium, or low findings.

## Notes

The broader existing DID export suite reached 12 S46 passes and 15 setup failures while S45 was concurrently changing header vocabulary. Every broader failure occurred during Modelo 111 registry hydration because current layout tokens `presenter_nif`, `page_complementaria`, `colegio_concertado`, and `aeat_seal` were rejected by the in-flight strict enum before DID behavior ran. That peer-owned S45 state is not claimed green and was not modified or staged by S46.
