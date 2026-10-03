# portal catalogue and annual prorrata register

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-148` · **Topic:** [Business and taxpayer domain](../topics/business-and-taxpayer-domain.md)

<!-- preserved:article -->
## Scope

This chunk covers 55 files, 3,252 manifest-counted lines, 133,407 bytes, and 30,892 measured tokens. All seven bounded pages were read through their listed ranges. This is static inspection only; I did not import or execute the application, modify `src/`, run tests, or verify AEAT destinations or legal content externally.

## Product capabilities

The notifications domain defines a typed, read-only reading for AEAT sanction/liquidation documents. It preserves the document’s identifiers, printed amounts, optional reductions, digest, and the distinction between an absent reduction and a printed zero. It computes the sum of the reductions that were actually supplied notification reading (`src/cadrumo/domain/notifications/sancion.py`).

The portals domain is a declarative catalogue, not a browser or filing client. It describes authentication gateways, tax procedures, borrador services, consultation pages, payments, and reference pages. Each entry binds a stable portal enum to a configured host, URL, category, accepted auth methods, URL-stability tier, translation keys, and active/retired lifecycle metadata. The catalogue includes the retired Modelo 037 entry pointing to Modelo 036 and separate entries for Renta Web, Pre303, filing forms, payments, notifications, and expediente/document consultation taxonomy (`src/cadrumo/domain/portals/categories.py`) retired Modelo 037 entry (`src/cadrumo/domain/portals/_entries/portal_m037_censal_simplificada.py`) portal metadata (`src/cadrumo/domain/portals/metadata.py`).

Entry construction resolves hosts and portal paths through centralized external constants and validates URLs as HTTPS. Individual metadata checks host equality, anonymous-auth exclusivity, filing/censo path shape, and retired/replacement consistency. Import-time registry assembly checks unique entries, complete enum coverage, key-to-entry identity, and valid `replaced_by` links. Lookups support one portal, category listings, and filing/borrador portals linked to a modelo through validated registry application links entry builder (`src/cadrumo/domain/portals/_entries/common.py`) single-entry checks (`src/cadrumo/domain/portals/metadata.py`) registry assembly (`src/cadrumo/domain/portals/registry.py`) modelo portal lookup (`src/cadrumo/domain/portals/registry.py`).

The prorrata register stores provisional and settled percentages per exercise and sector, the evidence/provenance for the provisional value, the annual volumes behind a definitive percentage, transition evidence for opting into or revoking special prorrata, operator-declared differentiated sectors, and evidence-carrying activity rows. Its precedence resolver selects an authorized or activity-start provisional percentage ahead of a carried prior definitive percentage and returns an explicit unresolved result if no candidate has a percentage. Coverage helpers require the explicit whole-entity entry plus every declared sector and, when the regime applies, the five official activity slots register entry models (`src/cadrumo/domain/prorrata_register/register.py`) precedence resolver (`src/cadrumo/domain/prorrata_register/register.py`) coverage helpers (`src/cadrumo/domain/prorrata_register/register.py`).

## How it works and knowledge

Portal identifiers and the entry tuple are authored locally; hostnames, filing paths, and the mappings from modelos to portals are supplied by external constants and the calculation registry. The registry sorts results for deterministic consumers and omits CENSO entries from the filing-dispatch query, while callers can list that category directly. The package documentation explicitly places live reads, writing, signing, and payment in application/adapter layers, outside this metadata contract portal scope boundary (`src/cadrumo/domain/portals/__init__.py`) registry-bound links (`src/cadrumo/domain/portals/registry.py`).

The prorrata register keeps taxpayer facts rather than statutory constants. Regime names, provenance types, transition kinds, sector letters, and their precedence are resolved from registry-owned catalogue helpers. It validates duplicate `(ejercicio, sector)` entries, duplicate sector definitions, duplicate activity identities/slots, interrupted-year field coupling, transition evidence consistency, and completeness helpers. Annual definitive arithmetic is delegated to the separate IVA calculation substrate; this module is the durable cross-period record and precedence selector registry-owned prorrata vocabulary (`src/cadrumo/domain/prorrata_register/register.py`) register uniqueness and transition checks (`src/cadrumo/domain/prorrata_register/register.py`) delegated calculation boundary (`src/cadrumo/domain/prorrata_register/__init__.py`).

Other domain row types keep filing input structured: M232 materializes row slots from the selected mapping, M349 separates NIF prefix from the exported number and checks GB/XI transition rules, M347 aggregates annual amounts by counterparty before applying its dated threshold, and M210 requires compatible grouped-renta facts. The reduction calculators for pension withdrawals and SAL/SLL reserve contributions take their parameters from the shared governed-fact context rather than duplicating those values in portal or register data M232 materialization (`src/cadrumo/domain/modelos/m232_row_materialisation.py`) M349 context and export (`src/cadrumo/domain/modelos/row_models.py`) M347 aggregate threshold (`src/cadrumo/domain/modelos/row_models.py`) fact context (`src/cadrumo/domain/modelos/modelo_fact_context.py`).

## Security and implementation assessment

Central host resolution and HTTPS/host checks constrain portal metadata to configured host families. The enum-to-entry coverage check makes a newly added portal impossible to silently omit from the catalogue. The records include auth-method descriptions, but they do not enforce authentication or authorize a live action; those decisions remain at the access-gate and application boundary host resolution (`src/cadrumo/domain/portals/hosts.py`) portal integrity refusals (`src/cadrumo/domain/portals/errors.py`).

The provisional prorrata resolver keeps “unknown” separate from zero, which prevents a missing historical percentage from becoming a guessed deduction rate. One local ambiguity remains: if two candidates have the same highest-precedence provenance but different percentages, `resolve_provisional_percentage` retains whichever appears first because it replaces the winner only for a strictly higher rank. The result is therefore input-order dependent for that case; the producer should guarantee at most one candidate per winning provenance or the resolver should reject conflicting peers winner selection (`src/cadrumo/domain/prorrata_register/register.py`).

Two evidence strings have only length constraints rather than nonblank validation: `ProrrataActivityRow.evidence_reference` and `ProrrataRegisterEntry.authorisation_reference` can accept whitespace-only values under their current field declarations. Transition evidence does explicitly reject whitespace-only references. If these are treated as durable proof locators, align their validators so an empty-looking reference does not satisfy evidence coupling activity reference (`src/cadrumo/domain/prorrata_register/register.py`) authorisation reference (`src/cadrumo/domain/prorrata_register/register.py`) transition reference validation (`src/cadrumo/domain/prorrata_register/register.py`).

The M232 mapping and M349 NIF-format helper use `today_madrid()` when selecting some registry declarations, while related M349 prefix validation accepts an explicit filing year/period. Confirm that workflows only use those current-date helpers for current filings or provide a filing coordinate when historical correction is needed. No tests are included in the assigned chunk, and static inspection cannot confirm external URL freshness or the correctness of current published tax instructions M232 date choice (`src/cadrumo/domain/modelos/m232_row_materialisation.py`) M349 NIF date choice (`src/cadrumo/domain/modelos/row_models.py`).

## Dependencies and follow-up

Keep portal host/path constants and model-to-portal application links synchronized with the curated entries; confirm retired entries retain useful historical links. Ensure prorrata seeding does not submit competing same-precedence candidates, reject blank authority/evidence locators, and apply the intended filing-period date for historical M232/M349 work. Confirm application code treats this package as metadata and uses the distinct live-access gates before remote navigation or actions.

## Complete assigned-file coverage

- notifications/__init__.py (`src/cadrumo/domain/notifications/__init__.py`)
- notifications/sancion.py (`src/cadrumo/domain/notifications/sancion.py`)
- portals/__init__.py (`src/cadrumo/domain/portals/__init__.py`)
- portals/_entries/__init__.py (`src/cadrumo/domain/portals/_entries/__init__.py`)
- portals/_entries/common.py (`src/cadrumo/domain/portals/_entries/common.py`)
- portals/_entries/portal_calendario_contribuyente.py (`src/cadrumo/domain/portals/_entries/portal_calendario_contribuyente.py`)
- portals/_entries/portal_cert_selection.py (`src/cadrumo/domain/portals/_entries/portal_cert_selection.py`)
- portals/_entries/portal_cert_validation_rest.py (`src/cadrumo/domain/portals/_entries/portal_cert_validation_rest.py`)
- portals/_entries/portal_clave_gestiones.py (`src/cadrumo/domain/portals/_entries/portal_clave_gestiones.py`)
- portals/_entries/portal_clave_idp_root.py (`src/cadrumo/domain/portals/_entries/portal_clave_idp_root.py`)
- portals/_entries/portal_clave_sede_entry.py (`src/cadrumo/domain/portals/_entries/portal_clave_sede_entry.py`)
- portals/_entries/portal_consulta_pagos.py (`src/cadrumo/domain/portals/_entries/portal_consulta_pagos.py`)
- portals/_entries/portal_dnie_sede_entry.py (`src/cadrumo/domain/portals/_entries/portal_dnie_sede_entry.py`)
- portals/_entries/portal_domiciliacion_bancaria.py (`src/cadrumo/domain/portals/_entries/portal_domiciliacion_bancaria.py`)
- portals/_entries/portal_m036_censal.py (`src/cadrumo/domain/portals/_entries/portal_m036_censal.py`)
- portals/_entries/portal_m037_censal_simplificada.py (`src/cadrumo/domain/portals/_entries/portal_m037_censal_simplificada.py`)
- portals/_entries/portal_m100_renta.py (`src/cadrumo/domain/portals/_entries/portal_m100_renta.py`)
- portals/_entries/portal_m111_retenciones_trabajo.py (`src/cadrumo/domain/portals/_entries/portal_m111_retenciones_trabajo.py`)
- portals/_entries/portal_m115_retenciones_arrendamientos.py (`src/cadrumo/domain/portals/_entries/portal_m115_retenciones_arrendamientos.py`)
- portals/_entries/portal_m123_retenciones_capital.py (`src/cadrumo/domain/portals/_entries/portal_m123_retenciones_capital.py`)
- portals/_entries/portal_m130_pago_fraccionado_ed.py (`src/cadrumo/domain/portals/_entries/portal_m130_pago_fraccionado_ed.py`)
- portals/_entries/portal_m131_pago_fraccionado_eo.py (`src/cadrumo/domain/portals/_entries/portal_m131_pago_fraccionado_eo.py`)
- portals/_entries/portal_m180_resumen_arrendamientos.py (`src/cadrumo/domain/portals/_entries/portal_m180_resumen_arrendamientos.py`)
- portals/_entries/portal_m190_resumen_trabajo.py (`src/cadrumo/domain/portals/_entries/portal_m190_resumen_trabajo.py`)
- portals/_entries/portal_m193_resumen_capital.py (`src/cadrumo/domain/portals/_entries/portal_m193_resumen_capital.py`)
- portals/_entries/portal_m200_sociedades_anual.py (`src/cadrumo/domain/portals/_entries/portal_m200_sociedades_anual.py`)
- portals/_entries/portal_m202_sociedades_fraccionado.py (`src/cadrumo/domain/portals/_entries/portal_m202_sociedades_fraccionado.py`)
- portals/_entries/portal_m232_vinculadas.py (`src/cadrumo/domain/portals/_entries/portal_m232_vinculadas.py`)
- portals/_entries/portal_m303_iva_autoliquidacion.py (`src/cadrumo/domain/portals/_entries/portal_m303_iva_autoliquidacion.py`)
- portals/_entries/portal_m347_operaciones_terceros.py (`src/cadrumo/domain/portals/_entries/portal_m347_operaciones_terceros.py`)
- portals/_entries/portal_m349_intracomunitarias.py (`src/cadrumo/domain/portals/_entries/portal_m349_intracomunitarias.py`)
- portals/_entries/portal_m369_oss_ioss.py (`src/cadrumo/domain/portals/_entries/portal_m369_oss_ioss.py`)
- portals/_entries/portal_m390_resumen_iva.py (`src/cadrumo/domain/portals/_entries/portal_m390_resumen_iva.py`)
- portals/_entries/portal_m720_bienes_extranjero.py (`src/cadrumo/domain/portals/_entries/portal_m720_bienes_extranjero.py`)
- portals/_entries/portal_m840_iae.py (`src/cadrumo/domain/portals/_entries/portal_m840_iae.py`)
- portals/_entries/portal_mi_area_personal.py (`src/cadrumo/domain/portals/_entries/portal_mi_area_personal.py`)
- portals/_entries/portal_mis_documentos_pendientes_firma.py (`src/cadrumo/domain/portals/_entries/portal_mis_documentos_pendientes_firma.py`)
- portals/_entries/portal_mis_expedientes.py (`src/cadrumo/domain/portals/_entries/portal_mis_expedientes.py`)
- portals/_entries/portal_mis_notificaciones.py (`src/cadrumo/domain/portals/_entries/portal_mis_notificaciones.py`)
- portals/_entries/portal_pago_autoliquidacion_cuenta.py (`src/cadrumo/domain/portals/_entries/portal_pago_autoliquidacion_cuenta.py`)
- portals/_entries/portal_pago_autoliquidacion_tarjeta_bizum.py (`src/cadrumo/domain/portals/_entries/portal_pago_autoliquidacion_tarjeta_bizum.py`)
- portals/_entries/portal_pago_liquidaciones_deudas.py (`src/cadrumo/domain/portals/_entries/portal_pago_liquidaciones_deudas.py`)
- portals/_entries/portal_pre303_ayuda.py (`src/cadrumo/domain/portals/_entries/portal_pre303_ayuda.py`)
- portals/_entries/portal_presentar_consultar_index.py (`src/cadrumo/domain/portals/_entries/portal_presentar_consultar_index.py`)
- portals/_entries/portal_renta_web_borrador.py (`src/cadrumo/domain/portals/_entries/portal_renta_web_borrador.py`)
- portals/_entries/portal_sede_root.py (`src/cadrumo/domain/portals/_entries/portal_sede_root.py`)
- portals/categories.py (`src/cadrumo/domain/portals/categories.py`)
- portals/codes.py (`src/cadrumo/domain/portals/codes.py`)
- portals/errors.py (`src/cadrumo/domain/portals/errors.py`)
- portals/hosts.py (`src/cadrumo/domain/portals/hosts.py`)
- portals/metadata.py (`src/cadrumo/domain/portals/metadata.py`)
- portals/registry.py (`src/cadrumo/domain/portals/registry.py`)
- prorrata_register/__init__.py (`src/cadrumo/domain/prorrata_register/__init__.py`)
- prorrata_register/protocols.py (`src/cadrumo/domain/prorrata_register/protocols.py`)
- prorrata_register/register.py (`src/cadrumo/domain/prorrata_register/register.py`)
<!-- /preserved:article -->
