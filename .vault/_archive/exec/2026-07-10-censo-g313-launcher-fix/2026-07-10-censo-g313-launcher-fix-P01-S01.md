---
tags:
  - '#exec'
  - '#censo-g313-launcher-fix'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:11d8b000c300b4c814d2e083441bac8d91a15433ae3cf957d4901bc3f96acfc4'
step_id: 'S01'
related:
  - "[[2026-07-10-censo-g313-launcher-fix-plan]]"
---

# Capture the authenticated MdcAcceso and es13 Mis Datos Censales HTML/trace with identity redacted, and record whether the MdcAcceso to es13 transition is a passive redirect or an active dispatch

## Scope

- `src/aeat/adapters/outbound/aeat/sede/tests/`

## Description

Captured the authenticated G313 launcher navigation on 2026-07-10 under the
warm live Cl@ve session, using read-only diagnostic drivers that reused the
production session seam (`ensure_authenticated_aeat_session` +
`storage_state_for_session` + `default_browser_session_factory`) inside an
`activate_master_key_provider(get_master_key_provider())` unlock. Every probe
emitted structure only — query-stripped URLs, HTTP status, censal-marker
presence, label names (never values), form/button/anchor inventory. No raw
censal HTML and no personal values were written to disk or the vault.

- Navigated to the configured launcher
  `sede.agenciatributaria.gob.es/wlpl/BUGC-JDIT/MdcAcceso` and captured HTTP
  status, final URL, and content at domcontentloaded, after networkidle, and
  after a 12s poll.
- Enumerated the landing page affordances (forms, buttons, anchors) and censal
  keyword presence.
- Navigated the authenticated sede `Censos, NIF y domicilio fiscal` section and
  the empresarios censal-trámites hub to enumerate the real censal gestión
  endpoints.
- Followed the personas-físicas Censos-WEB gestión
  (`OVCT-CXEW/DialogoRepresentacion?ref=/wlpl/BU36-ASIS/M036/index.zul`) to
  determine the real censal surface shape.

## Outcome

The captured transition is neither a passive redirect nor an active dispatch —
the configured launcher URL is simply wrong:

- **`/wlpl/BUGC-JDIT/MdcAcceso` returns HTTP 404** (`title = "Agencia Tributaria:
  404"`). The landing path never changed from the entry path, and
  `censal_marker_present` was false because the page is AEAT's 404 error page,
  not a censal page. The earlier `ERROR_SEDE_NAVIGATION` empty-parse was a
  symptom of a 404 URL.
- The session is genuinely authenticated: the logged-in operator's name renders
  in the sede chrome (recorded here only as "the operator's name was present",
  not the value). So the defect is purely the endpoint, not auth.
- There is no simple read-only "Mis datos censales" HTML endpoint on the
  authenticated sede. The real censal-data surfaces are ZK-framework (`.zul`)
  SPAs reached through a representation gate:
  `OVCT-CXEW/DialogoRepresentacion` renders "Selección del contribuyente a
  representar" (a chooser with an *en nombre propio* option and a CONFIRMAR
  button), and only after that confirm does the prefilled Modelo 036 ZUL
  (`BU36-ASIS/M036/index.zul` for personas físicas, `BU36-M036/MOD036/index.zul`
  general) load the censal data. The representation page carried `zul`/`zkau`
  markers and zero G313 label matches, confirming a ZK SPA, not label:value HTML.

Net: the fix is a re-point plus a driven representation-confirm plus a parser
re-grounding from HTML label-scraping to ZK-component extraction — materially
larger than the ADR's presumptive "wait for the es13 SPA" (option 1). P01's
capture-first gate prevented building that wrong fix.

## Notes

The ADR and plan are revised on the strength of these findings (chosen approach
moves from option 1 to the re-point + representation-drive + ZK-parser
re-grounding path), and the follow-up reference Blocker 1 is corrected from "no
readable censo / launcher access-gate landing" to the concrete 404 +
representation-gated-ZUL root cause. Diagnostic probe scripts live only in the
session scratchpad; nothing was added to the code tree. The full ZK extraction
and the representation-confirm drive are P02 work, not attempted in this step.
No sensitive value, raw censal HTML, or the operator identity was persisted;
no destructive git operations were run.
