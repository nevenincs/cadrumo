---
tags:
  - '#reference'
  - '#frontend-rental-rows'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:c5ff7c459db7170f00f926d5f621cf866599b409953206735a2103e52e7aba5c'
related:
  - "[[2026-11-12-frontend-rental-rows-adr]]"
---

# `frontend-rental-rows` reference: `Rental rows in the frontends: backend surface and frontend gaps`

What the backend serves for rental property rows, their leases and the ledger links to them, and what the window and TUI render for them, on `feature/tui` on 2026-11-12.

## Summary

- Sections: `renta_inmueble` (repeatable, effective-dated) at `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:1497`; `renta_arrendamiento` (repeatable) at `schema.toml:1718`, whose `inmueble` is the property's row index; `renta_inicial` and `renta_ultima_contrato_anterior` at `schema.toml:1827` and `:1837`. Section constants at `src/cadrumo/domain/contribuyente/inmueble_facts.py:43-44`; the rental section set at `src/cadrumo/application/user_profile/rental_records.py:49`.
- Retired tier: `renta_rental` is listed retired (`src/cadrumo/application/user_profile/tests/test_retired_profile_field_paths.py:21`, `src/cadrumo/domain/user_profile/schema_migration.py:127`).
- Writes: only the generic profile row operations `user-profile.repeatable-row-mutation`, `user-profile.repeatable-row-update`, `user-profile.repeatable-row-remove` (`src/cadrumo/application/user_profile/operations.py:217-241`, ids at `profile_operation_contracts.py:35-39`); read through `user-profile.view` (`view_operation.py:33`). No property- or lease-specific operation exists.
- Cross-row admission: a lease names an existing property, tenant ids are checked, a row is not removable while a ledger row references it (`rental_records.py:117`, `:138`, `:153`, `:204`). Refusals are locale keys `application.user_profile.errors.rental_*` (`rental_records.py:51-62`) whose `door` context names a CLI command (`rental_records.py:89`).
- CLI doors: `src/cadrumo/entrypoints/cli/config/inmueble.py:63,83,107,127` and `arrendamiento.py:74,94,112,131,151`; `arrendamiento end` is a CLI-only edit of `fecha_fin` (`arrendamiento.py:112`).
- Ledger links: `inmueble_ref` and `arrendamiento_ref` on `ledger.classify.single` (`src/cadrumo/application/ledger/classify_requests.py:39-40`, `:112-113`), on `ledger.classify.bulk` (`bulk_classify_operation.py:75`) and on manual transactions (`src/cadrumo/application/ledger/models.py:251-253`, `:404-405`); admitted against the profile by `rental_link_admission.py:57`. The refs are row-index tokens; no words are served for them.
- Words: profile field labels and enum choices are served (`src/cadrumo/application/user_profile/overview.py:376-377`); compound fields (`usos`, `valores_catastrales`, `mejoras`, `inquilinos`) are encoded strings with no structured rows.
- TUI: profile sections render generically (`src/cadrumo/entrypoints/tui/profile/overview_rendering.py:457-466`, `edit_screens.py:183`, `:277`); no property, lease or ledger-link field anywhere in `src/cadrumo/entrypoints/tui/ledger`.
- Window: profile sections render generically (`native/desktop/frontend/src/components/profile/ProfileDetails.tsx`, `src/shell/profileRows.ts:40-123`); the household editor maps only `renta_family` (`householdModel.ts:18-19`); `components/ledger/inspector/ClassifySection.tsx` has no link field.
- Not yet landed (lane branches): per-property Modelo 100 rows with `row_identity`, per-property carried-expense statements, the derived art. 23.2 reduction.
