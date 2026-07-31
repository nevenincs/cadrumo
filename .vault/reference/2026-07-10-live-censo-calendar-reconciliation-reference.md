---
tags:
  - '#reference'
  - '#live-censo-calendar-reconciliation'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:51eb2961b4844fc6e3ce82d8050b28d00cc2a9391a88e810796ed4438d683a8c'
related:
  - "[[2026-06-05-live-censo-calendar-reconciliation-plan]]"
---

# `live-censo-calendar-reconciliation` reference: `live censo G313 launcher blocker`

## Summary

On 2026-07-10 the live-censo-calendar-reconciliation plan finally obtained a
real authenticated Cl@ve Movil session against the operator's `me` profile and
ran the full live-read sweep (S10) plus the calendar projection (S11). The
read transport is proven end-to-end; two residual blockers remain, and NEITHER
is remaining implementation scope of the reconciliation plan. This reference
carries them so they do not rot.

## Blocker 1 — G313 launcher URL is a 404; real censo lives behind a representation-gated ZUL SPA

CONCRETE root cause (2026-07-10 authenticated capture, superseding the earlier
"lands on an access gate" framing): the configured launcher
`censo_g313_launcher = "/wlpl/BUGC-JDIT/MdcAcceso"` **returns HTTP 404** under a
valid authenticated session (`title = "Agencia Tributaria: 404"`). The landing
path never changes from the entry path and `censal_marker_present=false` because
the page is AEAT's 404 error page. The prior `config profile censo pull`
`ERROR_SEDE_NAVIGATION` empty-parse was a symptom of this dead URL, not an
access gate and not "no censo for this NIF".

- The session is genuinely authenticated (the logged-in operator's name renders
  in the sede chrome), so the defect is purely the endpoint.
- There is no simple read-only "Mis datos censales" HTML endpoint. The real
  censal-data surface is the prefilled Modelo 036 behind
  `www6.../wlpl/OVCT-CXEW/DialogoRepresentacion` — which renders "Selección del
  contribuyente a representar" (an *en nombre propio* chooser + CONFIRMAR
  button) — and only after that confirm does the ZK-framework (`.zul`) SPA
  (`BU36-ASIS/M036/index.zul` personas físicas, `BU36-M036/MOD036/index.zul`
  general) load the censal data. The representation page carried `zul`/`zkau`
  markers and zero G313 label matches, confirming a ZK SPA, not label:value HTML.

Consequence: the fix is (a) re-point the launcher to the representation-gated
036 flow, (b) drive the *en nombre propio* representation confirm, and (c)
re-ground the parser from HTML label-scraping (`parse_g313_html` /
`_G313_LABELS`) to ZK-component extraction — materially larger than a URL swap
or a wait-tweak. The censo-sync application (`_censo_sync.py`) and CLI verbs
(`_profile_censo.py`) remain correct; the defect is entirely in the outbound
sede launcher (`_censo_live.py`), the launcher constant, and the parser
(`_censo.py`). Full findings: exec `2026-07-10-censo-g313-launcher-fix-P01-S01`;
fix pipeline: `2026-07-10-censo-g313-launcher-fix-plan`.

## Blocker 2 — AEAT account is empty for 2026

Every live-read facade succeeded and persisted real snapshots, all returning
zero rows: notifications (`row_count=0`), filed list 2026 (0 usable rows),
filed pull 303/2026 (`captured_count=0`, `justificante_metadata_count=0`,
`filing_evidence_stamped_count=0`), expedientes 303/2026 (`declaration_count=0`),
justificante list (`count=0`).

Because no filed 2026 declaration exists in the authenticated account, positive
filed-history / justificante enrollment and positive submitted /
justificante-verified calendar rows are environmentally unobtainable. This is
account state, not a code gap: the read path is proven operational and the
calendar correctly refuses to fabricate submitted state (strict calendar
REFUSES on `censo.enrolment_unverified`; `--allow-incomplete` shows local
obligation rows only). Positive proof becomes producible once the account
carries a filed row to reconcile against.
