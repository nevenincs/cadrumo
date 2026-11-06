---
tags:
  - '#reference'
  - '#modelo-profile-bindings'
date: '2026-11-06'
modified: '2026-11-06'
body_schema: 'body-v2'
body_hash: 'sha256:7161435af589ae729241bc63430b20362c2d5285ef6f49d1de3a740c67f11722'
related:
  - "[[2026-11-06-modelo-profile-bindings-plan]]"
---

# `modelo-profile-bindings` reference: `Profile field coverage and runtime trace`

## Summary

The confirmed gap is the work-form projection of existing taxpayer header producers. Bank election, contact-person identity and official address component distinctions constrain which profile facts can be reused.

## Scope and method

MODELPROFILE examines canonical identity, contact, address and payment sources through typed registry declarations, calculation, work-form projection and export. Base eeba75569e252da8f3cd72826e1953740d386583, child branch nevenincs/modelo-profile-bindings. Semantic code search was attempted and returned index_unavailable for this child; targeted source inspection was used. The live typed inventory and verification results are added below when complete; static observations are not execution proof.

The committed discovery/context slices were rebased onto integrated TUI `9b456620bc` on 2026-11-06, becoming `579c45d185` and `4b24a414fb`. The inventory below describes the original pinned generation; final changed-path publication/adoption results must be recorded separately. The integration introduces public-name renames, not dependency changes. M720 generator/provenance changes were adapted and verified on this base; final results appear below.

## Runtime trace

Canonical identity paths are identity.tax_id, identity.name, identity.surnames and identity.legal_name. identity.email describes operator configuration contact, not the declaration contact. The contact section separately declares contact_person_name and contact_person_phone; the fiscal address is a coarse string with postcode. Source: `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:93` and `:252`.

Profile binding selection and typed value routing are owned by `src/cadrumo/application/modelo/profile_binding.py:370` and `:562`. Identity/export-addressed bindings are intentionally excluded from numeric channels. Bound text casillas use `src/cadrumo/application/modelo/profile_export_binding.py:164`; absent required values yield existing unresolved_binding diagnostics at `:251`. The same module shapes export dictionary fields and explicit taxpayer identity and declaration contact, at `:350`, `:434` and `:498`.

Calculation precedence overlays profile, backend, borrador and caller sources, retaining provenance, in `src/cadrumo/application/modelo/calculation_resolution.py:203`. No new missing-results contract is needed.

The concrete presentation disconnect: `src/cadrumo/application/modelo/work_form.py:279` creates LayoutWalker without a producer snapshot; `src/cadrumo/application/modelo/work_form_layout.py:71` defaults it to None, and `src/cadrumo/application/modelo/work_form_context_values.py:70` therefore returns None for producer-backed context fields. Registry-declared taxpayer fields in modelos 111, 115, 130 and 131 are context fields, not missing calculation casillas. Export already obtains profile identity through `src/cadrumo/application/modelo/export_accounts.py:672` and maps it through `src/cadrumo/application/filing/export_producer.py:945`.

## Semantic dispositions

| Field family | Canonical source | Current declaration/path | Role and disposition |
| --- | --- | --- | --- |
| Declarant NIF | identity.tax_id | taxpayer.tax_id export producer; M100 profile binding | Populate only declared taxpayer context; preserve absent facts |
| Person name | identity.surnames and identity.name | taxpayer.surnames, given_name, full_name and M100 formatted profile binding | Reuse canonical name composition; do not invent company/representative identity |
| Entity registered name | identity.legal_name with canonical entity shaping | taxpayer.legal_name or surnames_or_legal_name | Respect entity/person producer contract |
| Declaration contact | contact.contact_person_name and contact.contact_person_phone | contact producers | Separate person; no taxpayer fallback |
| Operator email | identity.email | Configuration contact | No automatic declaration-contact mapping without matching semantics |
| Fiscal address | contact.fiscal_address and postcode | Coarse profile facts; model-specific address shapes | No arbitrary splitting into AEAT coded components or third-party/property addresses |
| IBAN | Ledger own-account register | selected_account producers and explicit export choices | Charge/refund roles and per-filing selection remain authoritative; retired profile paths stay retired |
| Representative/other persons | Explicit role-specific facts | IRNR and detail-record producer families | Never substitute taxpayer identity |

## Evidence and coverage limits

The linked governing plan names accepted contracts. Existing tests provide real resolver examples in `src/cadrumo/application/modelo/tests/test_required_text_casilla_sources.py:85`, profile role/election examples in `test_profile_export_values.py`, and context producer examples in `src/cadrumo/application/storage/calc_sheets/tests/test_form_context_fields.py:92`. Existing work-form context tests cover year and absent binding, but lack the admitted profile-to-header path.

Official designs already bound to the sampled fields include AEAT DR 111 v18, DR 115 v13, DR 130 v12 and DR 131 2019-2023 v101 plus their revision-specific successors. This change must reuse their existing semantic producer assignments, rather than infer a new legal mapping from field labels. No new official release or supported-year policy is proposed.

The baseline inventory below is complete for its declared structural scope. The context and M720 repairs pass scoped source, publication and application proof below. Combined integrated acceptance remains CHECKS2-owned.

## Typed baseline coverage matrix

Enumerated 58 modelos and 161 authored revisions with zero hydration failures from PinnedAuthorityOperation.modelo_ids, modelo_directory, revision_with_export_layouts and form_layout. Generation: `e603740ab76ac811f108b398044d8111e9bf48086a584a657e6aa652a033d141`. The authority declares floor 2022, horizon 2026 and no hard ceiling; these are observed metadata, not a second support policy. The scan retains all 1,580 producer-key export fields (398 distinct keys), all 694 form-context references and 231 profile-binding occurrences. Historical authored revisions are enumerated even where the current support envelope refuses their original years. Temporal selection, not a lexical revision name, decides each supported filing year.

The following compact matrix groups exact authored revision IDs per modelo. Field columns list the exact generic producer suffixes; their canonical sources, roles and absence behavior are defined in Semantic dispositions above. A producer declaration already supplies export; a matching context reference was blank before this repair. Account fields continue to require explicit role selection. Other specialized producer keys are inventoried but not equated to generic profile facts. A dash means no declaration in that category, not an assertion that the official form needs none.

| Modelo | Authored revisions inspected | Taxpayer producer fields | Contact producer fields | Account producer fields | Profile identity/contact/address selector paths |
| --- | --- | --- | --- | --- | --- |
| 036 | 2022-hasta-2023-04-24, 2023-hasta-2025-02-02, 2025-02-03-y-siguientes | - | - | - | - |
| 038 | 2022-hasta-2024-05, 2024-desde-06, 2025-y-siguientes | - | - | - | - |
| 100 | 2020, 2021, 2022, 2023, 2024, 2025 | - | - | - | identity.name, identity.surnames, identity.tax_id, renta_spouse.birth_date, renta_spouse.disability_grade, renta_spouse.eu_eea_country, renta_spouse.eu_eea_resident, renta_spouse.name, renta_spouse.non_resident_irpf, renta_spouse.sex, renta_spouse.surnames, renta_spouse.tax_id |
| 111 | 2019-y-siguientes | given_name, surnames_or_legal_name, tax_id | - | iban | - |
| 115 | 2019-y-siguientes | given_name, surnames_or_legal_name, tax_id | - | iban | - |
| 117 | 2019-y-siguientes | given_name, surnames_or_legal_name, tax_id | - | iban | - |
| 122 | 2017-y-siguientes | given_name, surnames, tax_id | - | iban | - |
| 123 | 2019-2023, 2024-y-siguientes | full_name, given_name, surnames_or_legal_name, tax_id | - | iban | - |
| 126 | 2019-y-siguientes | given_name, surnames_or_legal_name, tax_id | - | iban | - |
| 128 | 2019-y-siguientes | given_name, surnames_or_legal_name, tax_id | - | iban | - |
| 130 | 2019-y-siguientes | given_name, surnames, tax_id | - | iban | - |
| 131 | 2019-2023, 2024, 2025, 2026, 2026-3t-4t | given_name, surnames, tax_id | - | iban | - |
| 136 | 2022-2025, 2026 | - | - | - | - |
| 145 | 2012-01-31-y-siguientes | - | - | - | - |
| 151 | 2015-2022, 2025-y-siguientes | full_name, given_name, surnames, tax_id | - | - | - |
| 156 | 2003-y-siguientes | tax_id | full_name, phone | - | - |
| 165 | 2013-2015, 2016-2022, 2023-2025, 2026-y-siguientes | tax_id | full_name, phone | - | - |
| 180 | 2019-2022, 2023-y-siguientes | full_name, tax_id | full_name, phone | - | - |
| 181 | 2022-y-siguientes | tax_id | full_name, phone | - | - |
| 182 | 2022-2023, 2024, 2025 | - | - | - | - |
| 184 | 2015, 2016-2018, 2019-2021, 2022, 2023-2024, 2025-y-siguientes | surnames_or_legal_name, tax_id | full_name, phone | - | - |
| 185 | 2003-2025, 2025-y-siguientes | surnames_or_legal_name, tax_id | full_name, phone | - | - |
| 187 | 2022-y-siguientes | - | - | - | - |
| 188 | 2022, 2023-y-siguientes | - | - | - | - |
| 189 | 2022, 2023, 2024, 2025 | tax_id | full_name, phone | - | - |
| 190 | 2022, 2023, 2024, 2025-y-siguientes | full_name, tax_id | - | - | - |
| 193 | 2022, 2023, 2024, 2025-y-siguientes | full_name, tax_id | - | - | - |
| 194 | 2019, 2023, 2024 | full_name, tax_id | - | - | - |
| 200 | 2022, 2023, 2024, 2025-y-siguientes | surnames_or_legal_name, tax_id | phone | - | - |
| 202 | 2019-2022, 2023-2024, 2025-y-siguientes | given_name, surnames_or_legal_name, tax_id | - | iban | - |
| 210 | 2023, 2024, 2025, 2026-y-siguientes | - | email, full_name, phone, secondary_phone | - | - |
| 216 | 2020-2023, 2024-y-siguientes | full_name, given_name, surnames_or_legal_name, tax_id | - | iban | - |
| 220 | 2022, 2023, 2024, 2025 | - | - | - | - |
| 222 | 2022, 2023, 2024, 2025-y-siguientes | surnames_or_legal_name, tax_id | phone | iban | - |
| 232 | 2016-2017, 2018-y-siguientes | given_name, surnames_or_legal_name, tax_id | - | - | - |
| 270 | 2013-2022, 2023-y-siguientes | legal_name | full_name | - | - |
| 280 | 2022-2024, 2025 | tax_id | full_name, phone | - | - |
| 296 | 2022, 2023, 2024-2025, 2026-y-siguientes | - | - | - | - |
| 303 | 2022, 2023, 2024-hasta-08-y-2t, 2024-desde-09-y-3t, 2025, 2026-hasta-01-y-1t, 2026-y-siguientes | full_name, tax_id | - | bank_address, bank_city, bank_country_code, bank_name, iban, swift_bic | - |
| 308 | 2009-2011-junio, 2011-julio-2015, 2016-2018, 2019-y-siguientes | surnames_or_legal_name, tax_id | - | - | - |
| 309 | 2004-2015, 2016-2017, 2018-2022, 2023-y-siguientes | full_name, tax_id | full_name, phone | - | - |
| 322 | 2008-2022, 2023, 2024-2025, 2026-y-siguientes | surnames_or_legal_name, tax_id | - | - | - |
| 341 | 2005-2015, 2016-y-siguientes | given_name, surnames, tax_id | full_name, phone | iban, swift_bic | - |
| 345 | 2022, 2023, 2024, 2025 | tax_id | full_name, phone | - | - |
| 347 | 2011-2024, 2025-y-siguientes | surnames_or_legal_name, tax_id | - | - | - |
| 349 | 2020-y-siguientes | full_name, tax_id | full_name, phone | - | - |
| 353 | 2021-hasta-2026-01, 2026-desde-02 | surnames_or_legal_name, tax_id | - | iban, swift_bic | - |
| 360 | 2010-y-siguientes | - | - | iban, swift_bic | - |
| 369 | esquema-exterior, esquema-importacion, esquema-union | full_name, tax_id | - | - | - |
| 390 | 2021, 2022, 2023, 2024, 2025, 2026 | given_name, surnames_or_legal_name, tax_id | - | - | - |
| 490 | 2021, 2022-1t, 2022-2t-4t, 2023-y-siguientes | full_name, tax_id | - | - | - |
| 576 | 2007, 2008-y-siguientes | full_name, tax_id | - | - | - |
| 604 | 2021-2023, 2024-y-siguientes | full_name, tax_id | - | - | - |
| 714 | 2021, 2022, 2023, 2024, 2025 | full_name, tax_id | - | iban | - |
| 720 | 2013-y-siguientes | full_name, tax_id | - | - | - |
| 721 | 2023, 2024 | - | - | - | - |
| 763 | 2012-2014, 2015-2017, 2018-1t-3t, 2018-4t, 2019-y-siguientes | - | - | - | - |
| 840 | 2003-y-siguientes | - | - | - | - |

### Field-level dispositions and coverage limits

The exact export field ID is the reference carried by each form context block; the repair resolves that reference and then its producer key. It does not infer a source from displayed headings or a modelo number. Examples are `modelo-111-page-01-nif` -> taxpayer.tax_id and `modelo-111-page-01-apellidos` -> taxpayer.surnames_or_legal_name, with the same official roles already used by export. Requiredness remains the field's registry declaration. Modelo 130's analogous fields are optional; no new requiredness is imposed.

M100's four authored editions already bind declarant identity to profile facts and have text-casilla and dictionary export resolution. Representative, spouse, asset-owner, issuer, creditor and group-entity rows are not generic taxpayer identity. The 600 lexical manual-input hints are discovery leads only; they are neither a defect count nor implementation authority. Inspected M390 representative/joint-declaration and M714 issuer/creditor candidates remain separately sourced. The scan does not certify every official field's legal completeness, test every export format, or adjudicate all specialized party/address keys.

The actual missing mapping identified separately is M720 revision `2013-y-siguientes`: `modelo-720.type_1.telefono-contacto` and `modelo-720.type_1.nombre-contacto` are manual text bindings, consumed by fixed-width export and form binding fields, while the profile declares contact.contact_person_phone/name with the same contact-person role. These fields are optional, and missing facts must remain absent. Explicit declaration overrides take priority. AEAT DR720, physical PDF page 6 (printed page 15), positions 59-67 and 68-107, identifies contact phone and surnames/name respectively. Official source checked 2026-11-06: `https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_Resto_Mod/archivos/modelo_720.pdf`; existing enrolled source aeat-dr-720 pins sha256 ac324b935b690f0b6fe12dc8351c324cc804170750f483b0768d6417dd4976b7 in `src/cadrumo/_data/registry/aeat/legal/foreign-assets.toml:178`. Final review corrected the initial Type-2 role interpretation: DR720 physical page 11, extraction lines 381-402, requires Type-2 NIF/name to repeat the Type-1 declarant. Those shipped manual inputs are supplied explicitly in the export fixture and are not claimed as automatic mappings by these two Type-1 contact replacements. Representative fields remain separately sourced.

A fresh form read resolves current profile facts for open work. Existing frontend ContextSummary renders backend value_text without identity matching or edit addresses (`native/desktop/frontend/src/components/modelo/form/RecordsBlock.tsx:95`). Returning from the profile page remounts and rereads the workspace. Cross-window profile updates do not push-refresh an already mounted workspace; that pre-existing limitation is separate from source resolution. Filed/discarded historical heads must not be presented with today's profile identity as if it were recorded filing evidence.

## Context repair verification

FRONTEND independently traced all three existing surfaces on integrated TUI `9b456620bc`: React `components/modelo/form/RecordsBlock.tsx` renders served `value_text` or the served unknown wording; TUI `entrypoints/tui/modelo/workbench/page_items.py` uses the same `context_value_text`; CLI `entrypoints/cli/modelo_rendering.py` renders the same work form. Thus removing a profile-backed field from generated form layout would remove it from all surfaces. The shared generator must retain those fields through existing read-only context, without surface-specific defaults. FRONTEND owns the additional React scenario assertions for served non-null/null context values; CHECKS2 owns their integrated build/run. Those assertions are pending, not completed evidence.

FRONTEND delivered the assertions in commit `14a3764b49` (`fix/dock-title-refit`) to CHECKS2. The four-language M347 scenario compares each numbered context field's displayed value with served `value_text` and asserts that first open does not issue `modelo.work.calculate`. Its conditional null expectation is not exercised by current fixtures (all M347/M303 context values are populated). This is an explicit React coverage limit; the child encrypted M720 scenarios separately cover absent/partial profile facts at the backend. Integrated frontend execution remains CHECKS2-owned.

The generator impact census reused the typed 58-modelo/161-revision inventory, checked actual source layout seed/review state and joined published export layouts with the two current M720 provider changes. Its fixed-width, nonrepeating scalar-profile predicates select exactly one generated revision: M720 `2013-y-siguientes`, contact fields `modelo-720-type_1-telefono-contacto` and `modelo-720-type_1-nombre-contacto` under `modelo-720-fichero-aeat` / `modelo-720-type-1`. Eleven profile-bearing authored/reviewed revisions across M130, M202 and M303 retain their authored layouts. XML/dictionary paths are outside this generator repair. Canonical generation and full validation below confirm this source-impact assessment.

Joining typed form context references to exact export fields identifies taxpayer/contact context in 31 modelos across 73 authored revision occurrences. Representative tests exercise 111, 115, 130, 131 and distinct M180 contact data. The original loader supplied no producer values and the original context resolver returned None for taxpayer.tax_id; the new loader test independently expects the synthetic profile identifier, so the original path cannot satisfy it.

The context slice's seven-module single-process pytest run passed 63 cases in 14.69 seconds. Three integration-marked exporter cases were excluded by default configuration; a follow-up explicit `-m 'unit or integration'` run of the new context tests and `test_export_producer_resolution.py` passed all 16 cases in 2.99 seconds, including those three. Ruff check, Ruff format check and scoped ty check passed all seven changed paths. Independent Sol high review found no actionable defects in this slice; full integrated gates remain CHECKS2-owned.

## M720 source installation and local validation

The final source changes the two Type-1 contact bindings to canonical profile providers, with exact instructional citations under `aeat-modelo-720-contact-instructions`. That guidance role reuses the enrolled PDF receipt without changing `aeat-dr-720` layout authority; the owning informative construct includes the guidance reference. Canonical generation changes only the two contact inputs to exact export-addressed read-only contexts and updates the source digest, preserving block IDs/order and export positions. A second generation writes zero fragments.

Normal creation opens the form without calculating. The admitted form-read path therefore supplies current profile values for these exact declared binding contexts when no saved answer exists; saved membership, including empty/false/zero, takes precedence. Historical/unusable forms receive no current-profile fallback. The read does not persist inferred values. Calculation separately persists the considered scalar profile fingerprints under the existing provenance contract.

Final source minimality/equivalence passed with fingerprint `53a5d5e136f483815d063c39a62ceab8fbeb2acbf176875f7f88361ed6f2133d` unchanged, 183518 bytes and 789 authored payload fields unchanged, zero redundant overrides/duplication/blocked work. The generic report's compaction status remains incomplete while minimality passes and source is accepted; no normalization was applied. `check-registry-target-current 720 2013-y-siguientes aeat-dr-720 2026 0A` passed with current output matching the committed target. Independent review passed the generated diff and construct evidence closure. Publication and encrypted runtime evidence follow.

The canonical publisher installed logical generation `29d247afb605e9ebce6bf596e9882186bb9296a55c28218e2d410375f17afeb5`, database SHA-256 `b407d7923479d11a68f893baeb56468f70fe607c23dcca616bf63e3c4af484cd` (121561088 bytes), into the explicitly selected child-local authority root. `check-bindings` passed in 57.096 seconds: 9001 bindings across 58 modelos, zero findings/limitations. `check-registry` passed in 125.438 seconds with recorded and candidate identities equal, eight lifecycle lanes passing and none failing; its nonblocking target-coverage lane remains partial with 56 excluded targets, 105 current and zero drifted/stale targets. Export placement covers 35870 fields in 493 records with zero gaps/overlaps. This is not a claim that excluded formatos gained export capability.

The seven-module scoped runtime selection initially passed 53 of 55 cases; two export cases lacked an explicit required Type-2 manual declaration row. A registered foreign-asset observation proved insufficient because its source row IDs are distinct from the shipped manual export fields. The final fixture uses the normal draft-input boundary for a synthetic Type-2 securities row and preserves the contact header solely from encrypted revision replay. It follows the existing case-preserving text codec. The nine-case encrypted module passed in 5.31 seconds. Independent review then corrected the fixture's Type-2 identity to repeat the canonical declarant; the two affected export cases passed in 2.84 seconds, with the other seven retaining unchanged passing evidence. Together these results cover all 55 scoped cases without claiming the earlier failing run passed.

The encrypted cases cover first-create/first-form without calculation or repository writes, populated/empty/phone-only profiles, saved caller precedence, considered profile fingerprints, fingerprint-sensitive revision identity, registry-enumerated support years and exact local export positions. The two authoring-boundary modules passed all 11 cases in 137.89 seconds. Scoped Ruff/format/ty and whitespace checks pass. Independent final Sol review is PASS for this candidate. CHECKS2 owns combined check-code, check-registry-gate, test-gate, full test-registry, React/native build acceptance, final authority/doc-fixture regeneration on integrated TUI, and integration/cleanup; no remote publication or push was performed.
