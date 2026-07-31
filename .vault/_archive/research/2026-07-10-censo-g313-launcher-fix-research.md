---
tags:
  - '#research'
  - '#censo-g313-launcher-fix'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:0221fef6c309a45873ac98fb82094a55aa1d4ae4df6d51596becd13ef1ced9b9'
related:
  - "[[2026-07-10-live-censo-calendar-reconciliation-reference]]"
  - "[[2026-06-05-live-censo-calendar-reconciliation-plan]]"
---

# `censo-g313-launcher-fix` research: `G313 Mis Datos Censales launcher lands on access page`

On 2026-07-10 the live-censo-calendar-reconciliation plan obtained a real
authenticated Cl@ve Movil session and ran `config profile censo pull`. It
reached AEAT but returned an empty `CensoFactSet` and refused with
`ERROR_SEDE_NAVIGATION`. This research grounds that failure in the outbound
G313 driver and identifies the root cause plus candidate fixes. The censo-sync
application logic and the CLI verbs are NOT implicated; the defect is in the
outbound AEAT sede driver.

## Findings

### Observed live failure

Under a valid session (`auth_persisted_session_state=live`,
`identity_alignment=matches`, `identity_kind=NIE`), the driver raised
`ERROR_SEDE_NAVIGATION` / `failure_mode=live_navigation_failed` with
`landing_host=sede.agenciatributaria.gob.es`,
`landing_path=/wlpl/BUGC-JDIT/MdcAcceso`, `censal_marker_present=false`,
`populated_field_count=0`.

### Root cause

The G313 launcher path in `src/aeat/core/external_constants.toml` is
`censo_g313_launcher = "/wlpl/BUGC-JDIT/MdcAcceso"` — the **Acceso** (access /
entry) page, not the censal data page. In
`src/aeat/adapters/outbound/aeat/sede/_censo_live.py`, `fetch_g313_censo` warms
the cookie jar on `Mis Expedientes`, then does a single
`page.goto(G313_LAUNCHER_URL, wait_until="domcontentloaded")` and immediately
calls `page.content()` + `parse_g313_html`. The captured `landing_path` was
identical to the entry path (`/wlpl/BUGC-JDIT/MdcAcceso`), so the client-side
redirect from the Acceso launcher into the authenticated `es13` Mis Datos
Censales SPA had **not** resolved when the HTML was captured. `MdcAcceso` is a
launcher/dispatch page whose real censal content loads via a subsequent
client-side navigation the driver never waits for or follows.

`_censal_marker_present(html)` returned `false`, confirming the captured HTML
carried none of the `_G313_LABELS` es13 field labels — the driver stopped on
the access page, not on the data SPA. This is consistent with the module's own
docstring hypothesis ("the launcher may need re-pointing or the parser labels
may need re-grounding").

### Why the existing waits are insufficient

The driver uses `PLAYWRIGHT_WAIT_DOMCONTENTLOADED`. `MdcAcceso` returns its DOM
immediately (a dispatch shell), so `domcontentloaded` fires before the es13
data navigation. The codebase already exposes
`PLAYWRIGHT_WAIT_NETWORKIDLE` and `aeat_browser_selector_probe_timeout_ms` in
`src/aeat/adapters/outbound/aeat/sede/_browser_constants.py`, and sibling
surfaces (notifications, declarations) wait beyond bare `domcontentloaded`. The
G313 driver does not.

### Candidate fixes (to be decided in the ADR)

1. **Wait for the censal SPA before capture.** After `goto(MdcAcceso)`, wait for
   a stable es13 content marker (one of `_G313_LABELS` / a known es13 selector)
   or `networkidle`, bounded by `aeat_browser_selector_probe_timeout_ms`, then
   capture `page.content()`. Lowest-risk: keeps the published Acceso entry point
   and simply lets the redirect resolve.
2. **Re-point the launcher** at the resolved es13 data URL if AEAT exposes a
   stable direct endpoint. Higher risk: the direct URL may be session/token
   scoped and less durable than the published Acceso entry.
3. **Follow the Acceso dispatch explicitly** (click/submit the access control if
   `MdcAcceso` renders one) then wait for the data page. Needed only if the
   transition is not a passive redirect.

Option 1 is the presumptive lead; the ADR must confirm the transition shape
against a captured authenticated `MdcAcceso` HTML/trace.

### Verification constraint (operator-gated)

Only the operator can exercise the live path (single real Cl@ve identity). Any
fix MUST be proven with: (a) a non-live regression using a captured/recorded
`MdcAcceso`-then-es13 navigation double through the existing
`browser_session_factory` seam in `_fetch_g313_censo_with_storage_state`, and
(b) one operator-run live `config profile censo pull` returning a populated
`CensoFactSet`. Capturing the real authenticated `MdcAcceso` + es13 HTML (with
identity redacted) is the first task, because the parser labels can only be
confirmed/re-grounded against the true data page.

### Scope boundary

In scope: `src/aeat/adapters/outbound/aeat/sede/_censo_live.py`, the launcher
path/markers in `src/aeat/core/external_constants.toml`, the parser labels in
`src/aeat/adapters/outbound/aeat/sede/_censo.py`, and their tests under
`src/aeat/adapters/outbound/aeat/sede/tests/`. Out of scope: the censo-sync
application (`_censo_sync.py`), the CLI verbs (`_profile_censo.py`), and the
calendar projection — all proven correct by the reconciliation plan.

### Update 2026-07-10 — P01 capture falsified the premature-capture hypothesis

The pre-capture root-cause above ("Acceso launcher; SPA redirect not resolved at
capture") is WRONG. The P01 authenticated capture
(`2026-07-10-censo-g313-launcher-fix-P01-S01`) found `/wlpl/BUGC-JDIT/MdcAcceso`
returns **HTTP 404** (`title = "Agencia Tributaria: 404"`) — it is a dead URL,
not a launcher that redirects late. The session authenticates correctly (the
operator's name renders in the sede chrome).

The real censal data is the prefilled Modelo 036 behind
`www6.../wlpl/OVCT-CXEW/DialogoRepresentacion` ("Selección del contribuyente a
representar" — an en-nombre-propio chooser + CONFIRMAR), which then loads a
ZK-framework (`.zul`) SPA (`BU36-ASIS/M036/index.zul` personas físicas,
`BU36-M036/MOD036/index.zul` general). The page carries `zul`/`zkau` markers and
zero G313 label matches — a ZK component tree, not `label:value` HTML.

Consequently candidate fix 1 (wait for SPA) is dead, fix 2 (re-point) is the
lead, and the parser must move from text-scraping to ZK-component extraction —
a larger change than first scoped. The ADR decision and the plan P02 steps were
revised accordingly on 2026-07-10.
