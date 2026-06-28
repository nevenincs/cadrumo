---
tags:
  - '#research'
  - '#portal-catalogue'
date: '2026-04-17'
modified: '2026-04-17'
related:
  - '[[2026-04-13-modelo-inventory-research]]'
  - '[[2026-04-13-modelo-inventory-adr]]'
  - '[[2026-04-12-submission-engine-adr]]'
  - '[[2026-04-12-setup-wizard-adr]]'
  - '[[2026-04-12-cert-auth-adr]]'
  - '[[2026-04-12-trilingual-i18n-adr]]'
---

# portal-catalogue research: AEAT Sede Electrónica portals and form URLs

Foundational research for Issue #7 (area:config, domain:local-state,
milestone 0.0.2-foundations). Inventories every AEAT (and adjacent)
portal this automation must interact with for Spanish autónomo and
small-SL tax filing. Output feeds the portal-catalogue ADR that
replaces the `submission_portal_hint: str | None` slot on
`ModeloMetadata` (#108) with a typed enum-based cross-reference.

## Methodology

Read-only research. Sources: (1) WebFetch of public AEAT pages at
`sede.agenciatributaria.gob.es/Sede/presentar-consultar-declaraciones-modelo.html`
and adjacent procedure indices on 2026-04-17, (2) existing repo
research under `.vault/research/` (modelo inventory, cert auth,
submission engine, setup wizard), (3) `aeat.domain.modelos._entries.modelo_*`
for the free-form `submission_portal_hint` strings already captured
in the modelo registry, (4) Orden HAC/1526/2024 (BOE-A-2025-410) for
the modelo 037 suppression fact. No live AEAT writes.

## Findings

### 1. Subdomain map

Six AEAT-family subdomains plus the adjacent whole-of-government
identity provider. Every Portal entry MUST bind to exactly one.

- `sede.agenciatributaria.gob.es` — canonical Sede Electrónica; hosts
  procedure landing pages under `/Sede/procedimientoini/G<code>.shtml`.
  `STABLE_PROTOCOL_GRADE` — URLs are BOE-referenced and rarely change.
- `www1.agenciatributaria.gob.es` — authenticated WebLogic shell
  (`/wlpl/...` actions) for Cl@ve-gated forms and drafts.
  `VOLATILE_APP_PATH` — paths can rotate across campaigns.
- `www2.agenciatributaria.gob.es` — second authenticated WebLogic shell
  used for certificate-gated presentation and some informative modules.
  `VOLATILE_APP_PATH`.
- `www3.agenciatributaria.gob.es` — Mi área personal mirror and
  notification viewer shell. `VOLATILE_APP_PATH`.
- `agenciatributaria.gob.es` / `www.agenciatributaria.es` — legacy
  informational landings, help, calendar, contact. `STABLE_WITHIN_CAMPAIGN`.
- `clave.gob.es` — whole-of-government identity provider
  (Cl@ve PIN, Cl@ve permanente, Cl@ve móvil). Adjacent, not AEAT,
  but in scope because the scraper must navigate through it.
  `STABLE_PROTOCOL_GRADE`.

### 2. G-code to modelo map (authoritative)

Every `ModeloCode` from #108 binds 1:1 to a procedure G-code at
`sede.agenciatributaria.gob.es/Sede/procedimientoini/G<code>.shtml`.
Modelo 037 is the only retired member (Orden HAC/1526/2024 effective
2025-02-03).

| ModeloCode | G-code | Portal category | Notes                                      |
|:-----------|:-------|:----------------|:-------------------------------------------|
| `036`      | `G322` | CENSUS          | Census declaration.                        |
| `037`      | n/a    | RETIRED         | Suppressed 2025-02-03; replaced by 036.    |
| `100`      | `G229` | IRPF_ANNUAL     | Renta anual; also has Renta Web borrador.  |
| `111`      | `GH01` | RETENCIONES     | Retenciones trabajo / actividades.         |
| `115`      | `GH02` | RETENCIONES     | Retenciones arrendamientos.                |
| `123`      | `GH04` | RETENCIONES     | Retenciones capital mobiliario.            |
| `130`      | `G601` | IRPF_FRACCIONADO| Pago fraccionado estimación directa.       |
| `131`      | `G602` | IRPF_FRACCIONADO| Pago fraccionado estimación objetiva.      |
| `180`      | `GI00` | INFORMATIVE     | Resumen anual retenciones arrendamientos.  |
| `190`      | `GI10` | INFORMATIVE     | Resumen anual retenciones trabajo.         |
| `200`      | `GE04` | SOCIEDADES      | IS autoliquidación anual.                  |
| `202`      | `GE00` | SOCIEDADES      | IS pago fraccionado.                       |
| `232`      | `GI43` | INFORMATIVE     | Operaciones vinculadas.                    |
| `303`      | `G414` | IVA_AUTO        | IVA autoliquidación; has Pre303 borrador.  |
| `347`      | `GI27` | INFORMATIVE     | Operaciones con terceros.                  |
| `349`      | `GI28` | INFORMATIVE     | Operaciones intracomunitarias.             |
| `369`      | `G420` | IVA_OSS         | OSS / IOSS ventanilla única.               |
| `390`      | `G412` | INFORMATIVE     | Resumen anual IVA.                         |
| `720`      | `GI34` | INFORMATIVE     | Bienes y derechos en el extranjero.        |
| `840`      | `G323` | IAE             | Impuesto actividades económicas.           |

### 3. Portal category taxonomy

Seven categories emerge. Each Portal member binds to exactly one.

- `AUTH` — entry points for Cl@ve, certificate, DNIe.
- `FILING` — per-modelo presentation procedures.
- `CENSUS` — census declarations (Modelo 036/037).
- `CONSULTATION` — Mi área personal, Mis expedientes, Mis notificaciones,
  Mis datos censales, Documentos pendientes de firma.
- `BORRADOR` — pre-filled drafts distinct from the presentation action
  (Renta Web, Pre303).
- `PAYMENT` — NRC-based payment flows, payment hub, domiciliación.
- `CALENDAR_REFERENCE` — Calendario del contribuyente, presentar-consultar
  index.

### 4. Auth method taxonomy

Seven orthogonal methods. A Portal carries a `frozenset[AuthMethod]`
naming the accepted method(s). `ANONYMOUS` = no auth required.

- `ANONYMOUS` — informational pages, G-code landings before the
  "Presentar" button.
- `CLAVE_PIN` — Cl@ve PIN one-shot code.
- `CLAVE_PERMANENTE` — Cl@ve permanent username/password.
- `CLAVE_MOVIL` — Cl@ve mobile OTP.
- `CERTIFICATE` — X.509 client certificate (FNMT, Camerfirma, etc.).
- `DNIE` — electronic national ID card; reuses the certificate flow
  technically but is a user-visible entry point worth modelling.
- `REFERENCE_NUMBER` — Renta Web "número de referencia" (box 505 of
  prior year's Renta) — limited to IRPF borrador flows.

### 5. URL stability taxonomy

Four tiers. Every Portal carries one `UrlStability` value so the
submission engine can skip self-healing probes on BOE-grade URLs
and prioritise them on VOLATILE ones.

- `STABLE_PROTOCOL_GRADE` — BOE-referenced procedure URLs; change only
  via explicit Orden publication. Most `sede.agenciatributaria.gob.es/Sede/procedimientoini/G*`.
- `STABLE_WITHIN_CAMPAIGN` — stable for a tax campaign year; can rotate
  when AEAT publishes the next-year campaign (e.g. Renta Web borrador
  entry, Pre303 help).
- `VOLATILE_APP_PATH` — WebLogic `/wlpl/...` action paths on `www1`/`www2`/`www3`;
  can rotate any time without notice.
- `RETIRED` — suppressed procedures (e.g. Modelo 037); retained for
  historical lookup but `active = False`.

### 6. Portal inventory

41 portal members: 8 AUTH + 20 FILING/CENSUS (19 active + 1 retired) +
2 BORRADOR + 4 CONSULTATION + 5 PAYMENT + 2 CALENDAR_REFERENCE. Each
captures: canonical URL, purpose, subdomain, auth methods, related
modelo code (or None), URL stability, trilingual labels (es
authoritative; en + hu target).

#### 6.1 Authentication (8)

- `PORTAL_SEDE_ROOT` — `https://sede.agenciatributaria.gob.es/` —
  Sede Electrónica landing. Subdomain `sede`. Auth `ANONYMOUS`.
  Modelo None. Stability `STABLE_PROTOCOL_GRADE`.
- `PORTAL_MI_AREA_PERSONAL` — `https://sede.agenciatributaria.gob.es/Sede/area-personal.html` —
  Mi área personal entry. Subdomain `sede`. Auth `CLAVE_PIN`,
  `CLAVE_PERMANENTE`, `CLAVE_MOVIL`, `CERTIFICATE`, `DNIE`. Modelo None.
  Stability `STABLE_WITHIN_CAMPAIGN`.
- `PORTAL_CLAVE_SEDE_ENTRY` — the `/clave/` handoff at AEAT that
  redirects to `clave.gob.es`. Subdomain `sede`. Auth `ANONYMOUS`.
  Modelo None. Stability `STABLE_WITHIN_CAMPAIGN`.
- `PORTAL_CLAVE_GESTIONES` — Cl@ve gestiones (password reset,
  registration). Subdomain `sede`. Auth `CLAVE_PERMANENTE`. Modelo None.
  Stability `STABLE_WITHIN_CAMPAIGN`.
- `PORTAL_CLAVE_IDP_ROOT` — `https://clave.gob.es/` IdP root.
  Subdomain `clave.gob.es`. Auth `ANONYMOUS`. Modelo None.
  Stability `STABLE_PROTOCOL_GRADE`.
- `PORTAL_CERT_SELECTION` — certificate selection entry under
  `www1.agenciatributaria.gob.es/wlpl/...`. Subdomain `www1`.
  Auth `CERTIFICATE`. Modelo None. Stability `VOLATILE_APP_PATH`.
- `PORTAL_CERT_VALIDATION_REST` — AEAT `@firma` / certificate validation
  REST endpoint. Subdomain `sede`. Auth `CERTIFICATE`. Modelo None.
  Stability `STABLE_WITHIN_CAMPAIGN`.
- `PORTAL_DNIE_SEDE_ENTRY` — DNIe gateway (reuses cert flow; modelled
  separately for user-visible distinction). Subdomain `sede`.
  Auth `DNIE`. Modelo None. Stability `STABLE_WITHIN_CAMPAIGN`.

#### 6.2 Filing procedures (19 active FILING + 1 CENSUS active + 1 retired)

For each active modelo: `https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G<code>.shtml`
with the G-code from §2. Subdomain `sede`. Auth `CERTIFICATE`,
`CLAVE_PIN`, `CLAVE_PERMANENTE`, `CLAVE_MOVIL`, `DNIE` (varies per
modelo; IRPF additionally accepts `REFERENCE_NUMBER`).
Stability `STABLE_PROTOCOL_GRADE`.

- `PORTAL_M036_CENSAL` → modelo `036` (category CENSUS).
- `PORTAL_M100_RENTA` → modelo `100`.
- `PORTAL_M111_RETENCIONES_TRABAJO` → `111`.
- `PORTAL_M115_RETENCIONES_ARRENDAMIENTOS` → `115`.
- `PORTAL_M123_RETENCIONES_CAPITAL` → `123`.
- `PORTAL_M130_PAGO_FRACCIONADO_ED` → `130`.
- `PORTAL_M131_PAGO_FRACCIONADO_EO` → `131`.
- `PORTAL_M180_RESUMEN_ARRENDAMIENTOS` → `180`.
- `PORTAL_M190_RESUMEN_TRABAJO` → `190`.
- `PORTAL_M200_SOCIEDADES_ANUAL` → `200`.
- `PORTAL_M202_SOCIEDADES_FRACCIONADO` → `202`.
- `PORTAL_M232_VINCULADAS` → `232`.
- `PORTAL_M303_IVA_AUTOLIQUIDACION` → `303`.
- `PORTAL_M347_OPERACIONES_TERCEROS` → `347`.
- `PORTAL_M349_INTRACOMUNITARIAS` → `349`.
- `PORTAL_M369_OSS_IOSS` → `369`.
- `PORTAL_M390_RESUMEN_IVA` → `390`.
- `PORTAL_M720_BIENES_EXTRANJERO` → `720`.
- `PORTAL_M840_IAE` → `840`.
- `PORTAL_M037_CENSAL_SIMPLIFICADA` → `037` (RETIRED 2025-02-03;
  `active = False`; `replaced_by = ModeloCode.MODELO_036`).

#### 6.3 Borrador / pre-filled (2)

- `PORTAL_RENTA_WEB_BORRADOR` — Renta Web borrador entry. Subdomain
  `www2`. Auth `CLAVE_PIN`, `CLAVE_PERMANENTE`, `CLAVE_MOVIL`,
  `CERTIFICATE`, `DNIE`, `REFERENCE_NUMBER`. Related modelo `100`.
  Stability `STABLE_WITHIN_CAMPAIGN`.
- `PORTAL_PRE303_AYUDA` — Pre303 IVA pre-filled aid. Subdomain `sede`.
  Auth `CERTIFICATE`, `CLAVE_PERMANENTE`. Related modelo `303`.
  Stability `STABLE_WITHIN_CAMPAIGN`.

#### 6.4 Consultation (4)

All under `sede` or `www3`, auth `CERTIFICATE` + `CLAVE_*`,
stability `STABLE_WITHIN_CAMPAIGN`, related modelo None.

- `PORTAL_MIS_EXPEDIENTES` — Mis expedientes.
- `PORTAL_MIS_NOTIFICACIONES` — Mis notificaciones.
- `PORTAL_MIS_DATOS_CENSALES` — Mis datos censales.
- `PORTAL_MIS_DOCUMENTOS_PENDIENTES_FIRMA` — Documentos pendientes de firma.

#### 6.5 Payment (5)

All auth-gated. Subdomain mostly `sede`; legacy hub on `www2`.

- `PORTAL_PAGO_AUTOLIQUIDACION_CUENTA` — pago en cuenta corriente.
- `PORTAL_PAGO_AUTOLIQUIDACION_TARJETA_BIZUM` — tarjeta / Bizum.
- `PORTAL_PAGO_LIQUIDACIONES_DEUDAS` — pago liquidaciones y deudas.
- `PORTAL_DOMICILIACION_BANCARIA` — domiciliación.
- `PORTAL_CONSULTA_PAGOS` — consulta de pagos / NRC.

#### 6.6 Calendar / reference (2)

- `PORTAL_CALENDARIO_CONTRIBUYENTE` — tax calendar.
- `PORTAL_PRESENTAR_CONSULTAR_INDEX` — presentar y consultar index.

### 7. Trilingual label discipline

Every Portal's `label: Translatable` carries `es`, `en`, `hu`. Spanish
is authoritative and uses AEAT's exact wording where possible (e.g.
"Mis expedientes", "Presentación Modelo 303"). English is the
code/docs authoritative rendering ("My case files", "Submit Modelo 303").
Hungarian is target user-facing language ("Aktáim", "303-as űrlap
benyújtása"). Labels live inside the per-entry pydantic model — no
gettext, no `.po` files (trilingual ADR 2026-04-12).

### 8. Cross-reference to #108 modelo registry

The #108 `ModeloMetadata` already carries a free-form
`submission_portal_hint: str | None` field. For the 19 active modelos
it points to the same G-code URL this research enumerates. The
portal-catalogue ADR must decide whether to:

- Option A: deprecate `submission_portal_hint` and add a typed
  `submission_portal: Portal` (breaks import cycle via
  `aeat.domain.modelos` → `aeat.domain.portals` — one-way, safe).
- Option B: keep both for one release then remove the hint string.

Either way, the unit test `test_casilla_cross_reference`-style pattern
(#108 exposes a similar closure test) is the template: for every
`ModeloCode` there must be exactly one `Portal` with a matching
`related_modelo`, and modelo 037 is the only permitted exception.

### 9. Open questions for the ADR

Ten items the ADR must resolve.

1. **Borrador vs presentation modelling.** Separate `Portal` members
   (higher fidelity, 2 extra entries) or one `Portal` per modelo with
   a `modes: frozenset[PortalMode]` field where `PortalMode ∈
   {PRESENT, BORRADOR, CONSULT, PAY}`? Recommendation in ADR: separate
   members — aligns with "one URL, one Portal" simplicity and matches
   the research enumeration.
2. **Cl@ve and DNIe as Portal entries?** Cl@ve surfaces four URLs
   AND four `AuthMethod` values. DNIe has no dedicated URL but is a
   user-visible option. ADR decision: Cl@ve gets 4 Portal entries for
   the surface URLs; DNIe appears as a `PORTAL_DNIE_SEDE_ENTRY`
   convenience member AND as `AuthMethod.DNIE` on gated Portals.
3. **`submission_portal_hint` migration path.** Replace with typed
   `submission_portal: Portal | None` now (#7 lands) or keep both
   fields during a deprecation window? Recommendation: replace
   immediately — no external consumers, hint never reached production.
4. **Retired portals — omit or retain?** Modelo 037 suppressed 2025-02-03.
   Retain with `active = False` + `retired_on: date` + `replaced_by:
   ModeloCode` for historical lookup and to keep the registry closure
   test total across all `ModeloCode` members (not just active ones).
5. **Extensible metadata pattern.** Match #108 exactly: one file per
   portal under `src/aeat/domain/portals/_entries/portal_<kebab>.py`,
   registry assembled at import time, frozen `MappingProxyType`,
   integrity check at import time. No exceptions.
6. **URL stability tiers.** Commit to the four-tier enum
   (`STABLE_PROTOCOL_GRADE`, `STABLE_WITHIN_CAMPAIGN`,
   `VOLATILE_APP_PATH`, `RETIRED`)? Recommendation: yes — drives
   self-healing sync priority downstream (2026-04-12-self-healing-sync-adr).
7. **Auth method taxonomy.** Commit to the seven-member `AuthMethod`
   enum? Recommendation: yes. `REFERENCE_NUMBER` is IRPF-only but
   deserves first-class modelling because it is the only method that
   does not require any credential infrastructure.
8. **Subdomain enum.** Six AEAT-family subdomains + `clave.gob.es`.
   Commit them to a closed `Subdomain` `StrEnum`? Recommendation: yes.
9. **URL validator.** How strict? Recommendation: pydantic `HttpUrl`
   via `PortalMetadata`, plus a custom validator that asserts the URL
   scheme is `https`, the host matches the declared `Subdomain`, and
   for `FILING` Portals the path matches `/Sede/procedimientoini/G[A-Z0-9]{3}\.shtml`.
10. **CLI surface.** Match `aeat.domain.modelos._cli` style: `aeat portals list`,
    `aeat portals show <member>`, `aeat portals for-modelo <code>`.
    Recommendation: yes — expose via `src/aeat/domain/portals/_cli.py`, register
    as a subcommand in `src/aeat/entrypoints/cli/__init__.py`.

### 10. Test coverage shape

Unit tests under `src/aeat/domain/portals/test_*.py` (Rust-style colocation).
Mandatory coverage:

- `test_codes.py` — every `Portal` member resolves via
  `get_portal(name)`; lookup errors raise `UnknownPortalError`.
- `test_metadata.py` — pydantic strict-validation invariants
  (HTTPS only, host matches subdomain, G-code path for FILING).
- `test_registry.py` — registry is frozen; every `Portal` has a
  registered `PortalMetadata`; no duplicates.
- `test_modelo_cross_reference.py` — every `ModeloCode` has at least
  one `Portal` whose `related_modelo` matches (or is the retired 037);
  every FILING `Portal`'s `related_modelo` is a valid `ModeloCode`.
- `test_cli.py` — CLI entry points emit deterministic JSON.
- `test_smoke.py` — public API surface check.

### 11. Scope cues for the ADR

- Subpackage: `src/aeat/domain/portals/` (already stubbed).
- Public API: `Portal` `StrEnum`, `PortalMetadata` pydantic v2 model,
  `PortalCategory`, `AuthMethod`, `UrlStability`, `Subdomain`
  `StrEnum`s, `PORTAL_REGISTRY`, `get_portal`, `portals_for_modelo`,
  `portals_by_category`, `UnknownPortalError`,
  `PortalRegistryError`.
- External dependency introduced: `aeat.domain.portals` imports
  `aeat.domain.modelos._codes.ModeloCode` (one-way). `aeat.domain.modelos` may also
  import `aeat.domain.portals.Portal` for the typed `submission_portal`
  field on `ModeloMetadata` — this creates a two-way dependency at
  the subpackage level but no cycle at the module level because the
  codes module is leaf.
- No new env vars.
- No live-write surface touched.
