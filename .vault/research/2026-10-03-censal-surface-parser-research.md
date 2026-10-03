---
tags:
  - '#research'
  - '#censal-surface-parser'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:ac1cee4084ba49436d536418c2b485f7fcf511e3766746794a6111e1ceb3669f'
related: []
---

# `censal-surface-parser` research: authenticated consultation map

All four census consultations rendered on 2026-10-03 after real Cl@ve Movil authentication in own-name mode. The existing landing-only reader omits reachable data. Only public labels and route paths are recorded here; taxpayer values remain in process memory and encrypted profile custody.

## Findings

### Four consultation surfaces are available

`https://www6.agenciatributaria.gob.es/wlpl/BUGC-JDIT/MdcAcceso` renders identity, fiscal address and notification address in titled tables. It offers Mis Actividades Economicas, Mi Situacion Tributaria and Mis Obligaciones. The obligations anchor has an onclick handler and no href; href-only discovery misses it.

Activities submit the existing fDatAct form to `/wlpl/TOAE-JDIT/EnlaceConsultaActividadesLocales`, targeting a new tab which lands at `/wlpl/TOAE-JDIT/ConsultaActividadesLocalesRelActividades`. Its table has Seccion, Epigrafe, Denominacion, Estado, F.Inicio, F.Baja, Locales and Num.Ref. The Locales consultation leads to `/wlpl/TOAE-JDIT/SvAlLocalesSesionQuery`; headers include address components, cadastral reference/type, surface area, degree of affectation, status, start/end dates and reference.

Tax status submits the same form to `/es13/s/buncbuncst00` in a new tab. After visiting activities, the first tax handoff reported an expired session; reloading MdcAcceso before the handoff succeeded without a second authentication. This proves the recovery, not its underlying cause.

Tax status contains fieldsets for IVA, IRPF, IS, IRNR, Ley 49/2002, withholdings, other taxes and intra-community special regimes. Rows use translated labels, casilla identifiers, rendered selected marks and dates in lists, not tables. JavaScript document.write renders selection marks; parsing script source as body text is incorrect. IVA includes applicable regimes, start declarations, deductions/prorrata and other options. IRPF includes instalment obligations and estimation methods. Unknown row labels must be retained rather than filtered out by a predefined inventory.

Obligations opens `/wlpl/BUGC-JDIT/ConsultaObligaciones`; its table has obligation description, periodicity, effective registration/end dates, last modification and status. All four surfaces were observed, not inferred from public help.

### Existing parser is narrower than the reachable service

`src/cadrumo/adapters/outbound/aeat/sede/censal_datos.py:217` parses only titled identity/address tables. `src/cadrumo/application/user_profile/censal_observation.py:57` has no consultation collection. The unavailable-regime conclusion in `2026-07-25-censal-profile-autofill-adr` is contradicted by this live observation and meets its stated reopening condition. The new evidence does not authorize filing, address modification, or representing another taxpayer.

### Parser options

Fixed coordinates and CSS widths are brittle. Label/header/casilla-driven records can retain reordered and newly added fields. Arbitrary redesign cannot be guaranteed; explicit shape refusal and retaining unresolved cells is preferable to guessing. A capture should carry surface identity, public source route and its original labels independently of any downstream tax interpretation.

## Sources

- Live authenticated routes named above, observed through bundled Playwright Chromium on 2026-10-03.
- `src/cadrumo/adapters/outbound/aeat/sede/censal_datos.py:217`
- `src/cadrumo/application/user_profile/censal_observation.py:57`
