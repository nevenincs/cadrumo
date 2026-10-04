---
tags:
  - '#adr'
  - '#modelo-360-solicitud-custody'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:2c29540545c6bf1afd2acc489eca143d5d5756c34be70f5c0d5296e831e73359'
related:
  - "[[2026-06-24-m303-refund-fichero-block-adr]]"
  - '[[2026-10-04-modelo-360-solicitud-custody-reference]]'
---

# `modelo-360-solicitud-custody` adr: `Modelo 360 solicitud facts and refund account in encrypted profile custody` | (**status:** `accepted`)

Accepted 2026-10-04 on the operator's approval, given that day, to build encrypted persisted storage for the modelo 360 refund application and bank-account data.

## Problem Statement

Modelo 360 could not be exported. The typed página 1 facts (`Modelo360ProfileFacts` in `src/cadrumo/application/filing/producer_snapshot_m360.py`) and the snapshot validator that requires them (`src/cadrumo/application/filing/producer_snapshot.py`, `_validate_modelo_360_snapshot`) existed, but nothing persisted them: the export path supplied `GeneralFilingProfileFacts` for every modelo outside 303, 202 and 111 (`src/cadrumo/application/modelo/export.py`, `_resolve_export_model_profile`), so the snapshot refused. The refund account had no store either: `ModeloIVAProfile.refund_account` is never populated from the profile projection (`src/cadrumo/domain/deadlines/profiles.py`, `_resolve_modelo_iva_profile`), and modelo 360 has no result casilla, so its disposition is the INGRESO fallback and no refund account was ever selected.

## Considerations

- DR360 campo 114 lets the refund account belong to the representante, and campo 116 makes the BIC obligatorio, so the 360 account is a fact of the solicitud rather than the taxpayer's standing IVA refund account (`2026-06-24-m303-refund-fichero-block-adr`).
- The solicitud header (destination Member State, causa, earlier registro number) changes per solicitud; the work unit addresses one solicitud per filing year and the revision's single `AD-HOC` period.
- An encrypted singleton register with revision-guarded mutation already exists for comparable operator-declared filing inputs (`src/cadrumo/adapters/persistence/profile/foreign_assets.py`, `src/cadrumo/adapters/persistence/profile/_secure_model_document.py`).

## Considered options

- Profile-schema fields on the user profile record: rejected; the facts are per solicitud and the account may be a third party's, which a taxpayer profile axis cannot express.
- Fields on the calculation revision's filing-instance evidence, as modelo 303 does: rejected for now; it reaches the calculation request, its content address and every calculate surface, which is disproportionate to header facts that never enter a formula.
- A dedicated encrypted singleton register keyed inside the payload by period: chosen.

## Constraints

- The register persists only through the registered `FINANCIAL` namespace `cadrumo.persistence.profile.modelo_360_solicitud`, bucket-local, structured custody, singleton key `default`; the period lives inside the ciphertext, never in a key.
- The account is the existing checksum-validated `RefundAccount`; the solicitud facts keep their own validators. An undeclared solicitud, an undeclared account or a missing BIC is a refusal, never a blank or default.
- The account is selected for the account page by the modelo's record design, not by inventing a refund disposition; the snapshot keeps refusing an account on any other non-refund filing.

## Implementation

We will persist `Modelo360SolicitudRegister` (entries of period, `Modelo360ProfileFacts` and an optional `RefundAccount`) through `Modelo360SolicitudRepository` on the bare-document secure-object kernel, expose it to export through `ModeloExportPorts.m360_solicitud`, and have the export resolve the entry for the work unit's period into the producer snapshot. The operator write surface (registered operation, CLI and TUI) is not part of this decision's first delivery and remains open.

## Rationale

The register mirrors a working analogue on the same storage kernel, keeps banking data in encrypted custody, and changes no calculation identity. Keying by period inside the payload matches how the work unit already addresses a 360 solicitud.

## Consequences

Modelo 360 export now passes the producer boundary from persisted facts. A later move of the facts into filing-instance evidence, or a second solicitud per period, would require a migration of this register. The published página 2 layout still refuses an ordinary solicitud at its page marker, which is a registry-layout matter outside this decision.
