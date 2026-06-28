---
tags:
  - "#reference"
  - "#auth-cli"
date: "2026-04-21"
modified: '2026-04-21'
related:
  - "[[2026-04-21-auth-cli-adr]]"
  - "[[2026-04-18-aeat-auth-providers-research]]"
  - "[[2026-04-18-auth-provider-abstraction-adr]]"
---

# Cl@ve portal reference — live capture 2026-04-21

Captured by driving Playwright against the real AEAT Sede + Cl@ve
portal for `feature/285-auth-cli`. Findings ground the
`ClaveMovilAuthProvider` implementation.

## Executive finding — AEAT no longer offers Cl@ve Permanente

AEAT's official identification page
(`https://sede.agenciatributaria.gob.es/Sede/identificacion-digital.html`)
today lists exactly these identification methods:

1. **Cl@ve Móvil** (replaces the legacy Cl@ve Permanente + Cl@ve PIN)
2. **Certificado y DNI electrónico**
3. **Número de referencia** (Renta-campaign only)
4. **Número de DNI/NIE con datos de contraste** (limited trámites)
5. **Sin identificación**
6. **Acceso ciudadanos UE (eIDAS)**
7. **TOKEN** (phone channel only)

Cl@ve Permanente is not listed in any AEAT entry page or auth-method
selector. The `clave.gob.es/clave-permanente` info page still exists
for other ministries, but AEAT Sede does not surface a Permanente
button on the `SelectorAccesos.html` chooser. The auth-provider
abstraction's earlier assumption that "Cl@ve Permanente is the
fully-headless low-friction path" must be retired for AEAT. **For
AEAT, Cl@ve == Cl@ve Móvil** (push/QR phone approval required).

## Auth selector URL template

```
https://sede.agenciatributaria.gob.es/static_files/common/html/selector_acceso/SelectorAccesos.html
  ?rep=S                # representation=allowed (can act on behalf of a third party)
  &ref=<url-encoded target path>
  &aut=CP               # accept certificate + Cl@ve
```

Example target paths:
- `/wlpl/TEWV-CORE/ResumenVlt` — Mis expedientes
- `/wlpl/BUGC-JDIT/MdcAcceso` — Mis datos censales
- `/wlpl/ZN01…` — Mis notificaciones (different entry)

The selector exposes exactly two buttons today:

| Button | `name` | `data-link` prefix |
|---|---|---|
| Cl@ve Móvil | `autoriza-P` | `https://www6.agenciatributaria.gob.es/wlpl/OVCT-CXEW/DialogoRepresentacion?ref=<target>` |
| Certificado o DNI electrónico | `autoriza-C` | `https://www1.agenciatributaria.gob.es/wlpl/OVCT-CXEW/DialogoRepresentacion?ref=<target>` |

Note subdomain split: `www6` for Cl@ve, `www1` for cert. Both hit
`/wlpl/OVCT-CXEW/DialogoRepresentacion` which arbitrates
representation consent before the real auth flow.

## Cl@ve Móvil flow — full trace

### Step 1 — auth selector
Click button `button[name=autoriza-P]` on `SelectorAccesos.html`.

### Step 2 — QR page
Navigates to
`https://www2.agenciatributaria.gob.es/wlpl/MOVI-P24H/ObtenerClaveMovilQR?ref=<double-encoded-target>`

The QR page exposes:

- **QR image**: `<img id="imgQRAcceso">` — the QR code to scan with
  the Cl@ve app.
- **Verification code**: `<span id="spanCodigoVerificacion">` — 3-letter
  code (e.g. "YLL") that the user cross-checks on the phone before
  approving.
- **Countdown**: `<span id="spanCuentaAtrasMinutos">` /
  `<span id="spanCuentaAtrasSegundos">` — ~5 minute window.
- **Cancel button**: `#botonCancelar`.
- **Alt path link**: "continuar con la autenticación por Cl@ve móvil
  sin lectura del QR" →
  `https://www12.agenciatributaria.gob.es/wlpl/MOVI-P24H/ObtenerClaveMovil?qAA=2&ref=<double-encoded-target>`
  (non-QR push path; see step 2-alt below).
- **Hidden form values**:
  - `hiddenTokenClaveMovil` — server-side token for the auth request.
  - `hiddenURLRef` — the post-auth redirect URL (provider-agnostic
    target).
  - `hiddenFrom` — constant `"aeat"`.
- **Polling endpoints** (inlined in the page's JS):
  - `ValidarClaveMovilQR` — POST, returns `{estadoPeticion, urlRef,
    mensajeRespuesta, codigoVerificacion}`; polled every few seconds
    by the page's own JS.
  - `CancelarClaveMovilQR` — POST to cancel.
  - `CaducarClaveMovilQR` — POST when the 5-minute window elapses.

### Step 2-alt — non-QR fallback (`qAA=2`)
Landing page:
`https://www2.agenciatributaria.gob.es/wlpl/BUCV-JDIT/AutenticaDniNieContrasteh?ref=...`

Form `#formAutenticaDebil` POSTs to itself. Fields:

| Input | Purpose |
|---|---|
| `input[name=NIF]` (required, maxlength 9) | DNI or NIE |
| `input[name=FECHA]` (date) | DNI validity / expiry date (for DNI holders) |
| `input[name=SOPORTE]` (maxlength 9) | NIE "número de soporte" from the document (for NIE holders) |
| `button#botonContinuar` | Submit |

Hidden: `AZUL`, `FECHANIE`, `LLAMADAWSNIE`, `ref`, `formatoError`.

After submit, AEAT issues a push notification to the Cl@ve app
registered to that DNI/NIE. Kent approves on the phone; the page
auto-redirects to `<ref>`.

### Step 3 — approval + redirect
When the Cl@ve app reports "approved" (QR or push), the polling JS
on the QR page detects `estadoPeticion=APPROVED` and navigates to
`hiddenURLRef`. Final landing is the target surface (e.g. Mis
expedientes at `www6.agenciatributaria.gob.es/wlpl/TEWV-CORE/ResumenVlt`).

Session cookies are set on `*.agenciatributaria.gob.es` and are
captured by Playwright's `storage_state()`.

## Implementation strategy for `ClaveMovilAuthProvider`

Do NOT reimplement the polling loop in Python/httpx — that rebuilds
a hostile surface (session tokens, CSRF, JS-only cookies). Instead,
let Playwright navigate the existing web JS and just **wait for the
post-approval URL** to appear. Kent sees the QR + verification code
in his terminal; the provider blocks on `page.wait_for_url(<target>,
timeout=5 min)`.

Minimum flow:

1. Accept two optional Settings (for the non-QR fallback only):
   `aeat_clave_movil_dni_nie: str | None`, plus either
   `aeat_clave_movil_dni_fecha: date | None` or
   `aeat_clave_movil_nie_soporte: str | None`.
2. `authenticate()`:
   1. Open Playwright context.
   2. Navigate to the selector URL. Take the target from
      `settings.aeat_sede_expedientes_path` (joined to `https://sede.agenciatributaria.gob.es`).
   3. Click `button[name=autoriza-P]`.
   4. Wait for the QR page. Extract:
      - `document.querySelector('#imgQRAcceso').src` (data:image/png;base64,...)
      - `document.querySelector('#spanCodigoVerificacion').textContent`
      - `document.querySelector('#hiddenURLRef').value` — the final target.
   5. Render to Kent's terminal:
      - QR code — convert base64 PNG to a terminal-friendly ASCII QR
        with `qrcode` (pure Python, no binary dep). The provider
        decodes the base64, feeds bytes to `qrcode` using the URL
        embedded in the QR (or we can regenerate one from
        `hiddenTokenClaveMovil`).
      - Verification code (big text, colored) — "Confirm this code
        on your phone: **YLL**".
      - Countdown hint.
   6. `page.wait_for_url(<target pattern>, timeout=settings.aeat_clave_timeout_ms)`.
   7. On success, capture `storage_state` via the existing
      `AeatAuthenticator._capture_storage_state_locked` path.
3. If the user is on a phone-unfriendly setup and has set
   `AEAT_CLAVE_PREFER_NON_QR=1`, bypass step 4 by clicking the
   "continuar sin QR" link and filling the DNI/NIE + FECHA/SOPORTE
   form automatically, then waiting for the same redirect.

## Session persistence

AEAT cookies set on `*.agenciatributaria.gob.es` are
provider-agnostic. Playwright's `storage_state()` captures them all,
and the existing
`_capture_storage_state_locked()` / `_resume_from_storage_state_locked()`
round-trip already works for certificates. For Cl@ve the stored
record needs the cert-specific fields to be optional (see
`_PersistedSessionMetadata` generalisation task). Idle TTL on AEAT
Sede is 18 minutes; the same `AEAT_SESSION_IDLE_TTL` constant
applies.

## What's NOT in scope

- Cl@ve Permanente provider — AEAT no longer surfaces it; tracked as
  a dead end for Kent's AEAT workflow. Other gov APIs (Seguridad
  Social, DGT) still support it, but that's a different integration
  target.
- DNI/NIE con datos de contraste as a standalone provider — limited
  to a subset of trámites that does not include Mis expedientes /
  Mis notificaciones. Same phone-based push-approval chain hides
  under it anyway, so Cl@ve Móvil covers the same ground.
- Registering a new Cl@ve identity — outside AEAT; user action only.

## Assumptions vs live-verified reality

Three assumptions the pre-PR-#285 codebase inherited from ADR research
were refuted on first live contact with AEAT Sede on 2026-04-21. All
three bit us during the Cl@ve Móvil bring-up; similar assumptions
almost certainly remain in downstream code (status reader,
justificante verifier, submission engine) and must be audited before
those surfaces are unlocked.

### 1. "`SelectorAccesos.html` is auth-gated"
**Wrong.** `https://sede.agenciatributaria.gob.es/static_files/common/html/selector_acceso/SelectorAccesos.html?rep=S&ref=<target>&aut=CP`
is **static HTML**. It always serves HTTP 200 regardless of cookie
state, and always renders the "Cl@ve Móvil" and "Certificado" buttons.
The only way to tell whether a session is live is to click a button
(or navigate to its `data-link`) and inspect where AEAT lands.

Fix in PR #285: `ClaveMovilAuthProvider.verify()` now prefers the
concrete post-auth URL (`landing_url` captured at login) as the probe
target; it checks `status 2xx/3xx AND target_path in landing_url AND
"SelectorAccesos" not in landing_url`.

### 2. "`/wlpl/<app>/<handler>` paths live on `sede.agenciatributaria.gob.es`"
**Wrong.** `sede.agenciatributaria.gob.es/wlpl/TEWV-CORE/ResumenVlt`
returns HTTP 404. The `/wlpl/...` paths are served by the AEAT
WebLogic application cluster at `www<N>.agenciatributaria.gob.es`
(observed `www1`, `www2`, `www6`, `www12`). The `sede` host is the
static / content front-end; the `www<N>` hosts are the app
back-ends. AEAT's dispatcher
(`/wlpl/OVCT-CXEW/DialogoRepresentacion?ref=…`) picks the subdomain
during login.

Fix: `_ClaveMovilSidecar` now persists the concrete
`landing_url` observed after authentication so resume probes hit the
exact host + path AEAT served last time.

### 3. "The post-auth target URL is stable across sessions"
**Partially wrong.** The path segment (`/wlpl/TEWV-CORE/ResumenVlt`)
is stable, but the subdomain (`www<N>`) may rotate per session due
to AEAT's load balancer. A probe that hard-codes `www6` may fail
next week against the same session. Persisting the actual
`landing_url` per session and using it as the resume probe target is
the safe approach; if future probes 404, the resume path should
fall back to the selector-dispatch flow (click through the button)
rather than assume the subdomain.

### Known-risk code sites (not yet audited)

- `src/aeat/status/_reader.py:177` — `StatusReader._fetch_html` uses
  `urljoin(self._settings.aeat_base_url, path)` where
  `aeat_base_url = https://sede.agenciatributaria.gob.es`. Every
  status surface (`expedientes`, `notificaciones`, `devoluciones`,
  `borrador`, `datos-fiscales`, `calendario`) passes a `/wlpl/...`
  path and will 404 exactly like our Cl@ve probe did.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py:431` — the certificate provider's
  `verify_handshake()` and `verify()` probes target
  `Settings.aeat_certificate_verify_url` (default
  `https://sede.agenciatributaria.gob.es/`). The handshake test is
  fine (mTLS is domain-level); the login-verification semantics
  probably are not, but cert auth is on hold pending Kent's FNMT
  renewal so no user is hitting this today.
- `src/aeat/entrypoints/cli/submission/_helpers.py:108` — presentation URL
  `f"https://sede.agenciatributaria.gob.es/modelo-{modelo}"` is a
  placeholder and needs live verification before submission dry-run
  output is trusted.
- `Settings.aeat_status_detail_url_template` (default
  `/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}`) — will
  inherit the same host-assumption bug when plumbed into the reader.



- **STORK**: pan-European auth federation. `storksp=EA0028512` is
  AEAT's service-provider code.
- **qAA** (quality Assurance level): Cl@ve identity assurance level.
  `qAA=2` = substantial (DNI/NIE + registered Cl@ve app push).
- **OVCT-CXEW**: AEAT's representation-consent servlet family.
- **MOVI-P24H**: AEAT's Cl@ve Móvil orchestration servlet family.
- **BUCV-JDIT**: AEAT's DNI/NIE weak-authentication servlet family.
