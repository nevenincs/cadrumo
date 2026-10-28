---
tags:
  - '#plan'
  - '#profile-field-remap'
date: '2026-10-27'
tier: L1
related:
  - '[[2026-08-10-current-schema-only-purge-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-10-23-desktop-ledger-editor-adr]]'
  - '[[2026-10-27-profile-field-remap-iva-usage-share-adr]]'
modified: '2026-10-27'
body_schema: body-v2
body_hash: 'sha256:45bf7a1f024fa243664a572b7676abf74a40f2b763f7b874b7f49a94c0fc2efd'
---

# `profile-field-remap` plan

Delete unused profile fields, explain every field from text the backend already holds, and make the desktop a pure remapping of backend-served values.

## Description

Approved 2026-10-27. Basis: the user instructed on 2026-10-27 to delete every profile field nobody uses, to remap existing backend help and labels instead of authoring new text, and ruled that the desktop frontend holds no data or logic of its own and only remaps values the backend serves to the CLI and TUI.

Audit result (2026-10-27, every field of `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml` version 7, 179 fields; dotted-path, bare-key, attribute, registry-binding and deadline-hydration readers traced). S01 deletes these fields because no production reader decides, computes, exports, warns or gates on them:

- Whole sections: `usage_ratios` (`category_id`, `business_ratio`; the live ratios are the ledger `UsageRatioProfile` store), `properties` (`cadastral_reference`, `use_type`), `attribution_entity` (`legal_form`).
- `identity.notes`; `contact.fiscal_address_is_habitual_vivienda`; `censo.establecimiento_type`; `censo.elected_withholding_pct`; `activities.cnae`; `attribution_entity_socios.role`.
- `taxpayer_type.sal_socios_trabajadores_count`, `sal_reserva_especial_dotada`, `sal_capital_social` (the SAL calculation takes command inputs instead).
- `taxpayer_type.ley_49_2002_special_regime_option_declared`, `_option_date`, `_renunciation_declared`, `_renunciation_date`.
- `irpf.professional_income_withholding_ge_70pct`; `irpf.objective_estimation_modulos_iae_epigraph`; `irpf.objective_estimation_modulos_module_1_units` through `module_7_units`.

Kept deliberately: fields bound only by historical registry revisions (for example Modelo 100 2022 spouse bindings, Modelo 303 2022 `iva.autoconsumo_promotor_base`), because historical revisions remain live authority; `renta_family.ascendants`, which a registry binding still names; `attribution_received.entity_nif`, `entity_name`, `share_pct`, which identify the repeated row to the operator.

Decision coverage: field deletion is routine execution under `2026-08-10-current-schema-only-purge-adr` (pre-release, current schema only; no migration of old stored shapes). S06 records the user's frontend ruling as an amendment of `2026-10-04-desktop-shell-adr`; S07 to S10 execute under it and under `2026-10-23-desktop-ledger-editor-adr`. Help remap (S03, S04) reuses existing localized copy: setup-wizard prompts, help and choice descriptions keyed by each question's `profile_key`, section summaries, and the registry category `label` and `notes` keys; it authors no new explanatory text.

## Steps

- [x] `S01` - delete the audited dead and collected-only profile fields and every consumer (wizard questions, setup mapping, deadline hydration, labels, locales, fixtures, tests); `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`.
- [x] `S02` - delete unread deadline-model attributes and the retired default_ratio concept, including the desktop standard-ratio column; `src/cadrumo/domain/deadlines/models.py`.
- [x] `S03` - remap profile field help from the setup-wizard question copy keyed by profile_key, replacing the eight-path help allowlist for TUI, CLI and desktop; `src/cadrumo/domain/user_profile/labels.py`.
- [x] `S04` - serve category label, notes and proportionality kind from the registry in ledger.ratios responses and render them in the Ratios pane; `src/cadrumo/application/ledger/ratios.py`.
- [x] `S05` - apply the usage ratio exactly once through the category rule evaluator for annual Renta and Modelo 130 (user ruling 2026-10-27: the ledger usage-ratio store and registry rule own the ratio; a row business_pct no longer scales usage-ratio categories), proven by tests through the real resolvers; `src/cadrumo/application/aggregation/renta_ledger.py`.
- [x] `S06` - amend the desktop shell ADR: the window holds no domain data or domain logic and only remaps values the backend serves to CLI and TUI; `.vault/adr/2026-10-04-desktop-shell-adr.md`.
- [ ] `S07` - replace frontend ledger vocabularies and usage-ratio category lists with served backend vocabularies; `native/desktop/frontend/src/shell/ledgerVocabulary.ts`.
- [ ] `S08` - replace frontend classification availability, field routes, clearing and identity rules with backend-served contract data; `native/desktop/frontend/src/shell/ledgerCommands.ts`.
- [ ] `S09` - replace frontend invoice arithmetic, retention, validation facts and the IVA rate table with a backend invoice preview operation; `native/desktop/frontend/src/components/ledger/invoices/invoiceModel.ts`.
- [ ] `S10` - replace frontend rule-pattern matching, percent and period grammar with backend previews and served grammar; `native/desktop/frontend/src/components/ledger/setup/setupModel.ts`.
- [x] `S11` - ground the IVA deductibility of home-office suministros in official AEAT or DGT criteria and correct the IVA share, which today carries the IRPF-only 0.30 factor (user ruling 2026-10-27: ground first); `src/cadrumo/application/aggregation/iva_ledger.py`.
- [x] `S12` - audit every category deductibility rule (IRPF proportionality, statutory multiplier, IVA treatment, citations, locale notes) against bundled official sources and correct each wrong rule (user instruction 2026-10-27: fix all deductibility rules); `src/cadrumo/_data/registry/aeat/facts/0064-categories-profile.toml`.

## Parallelization

S01 then S02 then S03 are serial: they share the schema, labels, wizard and locale files. S04, S05 and S06 are independent of them and of each other. S07 to S10 follow S06 and are serial, because they share the desktop ledger shell modules.

## Verification

- No production reader remains for a deleted field, and the schema, wizard, setup mapping, deadline model, labels and the four locale catalogues agree (locale parity and schema parity tests pass).
- Every profile field that has setup-wizard copy shows that copy as help in the TUI, desktop and CLI through one backend producer; no new explanatory strings are authored.
- The home-office ratio is applied once on MIXED rows, proven by a test through the real Renta resolver.
- The desktop frontend contains no copied vocabulary, rate table, classification rule or tax arithmetic; each is served by a backend operation the CLI or TUI also uses, and the frontend parity tests that guarded copies are removed.
- `just check-import-boundaries`, `just check-style`, `just check-format`, `just check-types` and the covering Python and frontend tests pass.
