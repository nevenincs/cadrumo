---
tags:
  - '#adr'
  - '#censo-g313-launcher-fix'
date: '2026-07-10'
modified: '2026-07-15'
body_hash: 'sha256:aa627e859e5846003902755a4c588d12e2d4b321ff21b96b66e6c7a4b9bd1a8e'
superseded_by: '2026-07-11-censo-operator-manual-enrolment-adr'
related:
  - "[[2026-07-10-censo-g313-launcher-fix-research]]"
---

# `censo-g313-launcher-fix` adr: `re-point censo read to the representation-gated Modelo 036 ZUL and re-ground the parser` | (**status:** `superseded`)

> **Superseded 2026-07-11 by `2026-07-11-censo-operator-manual-enrolment-adr`.**
> An authorized Fable architecture pass (on operator delegation) rejected this
> ADR's chosen approach: the P02.S04 capture proved that reading census data
> requires operating AEAT's "Censos WEB" *modification* ZKoss tool, which
> `aeat-safety-legal-gates` prohibits (a read that is one accidental submit from
> mutating census state is a live-write path with extra steps). The ruling is
> Option 4 — retire the live censo scrape; censal facts become operator-manual;
> the calendar's `censo.enrolment_unverified` posture is the honest end state.
> This ADR and its L2 fix plan are closed by supersession.

## Problem Statement

The outbound censo driver reads `censo_g313_launcher =
"/wlpl/BUGC-JDIT/MdcAcceso"`, which the P01 authenticated capture proved
returns **HTTP 404** — a wrong/non-existent AEAT URL. The empty `CensoFactSet`
and the `ERROR_SEDE_NAVIGATION` refusal were symptoms of a dead URL, not of a
premature capture (the original hypothesis, now falsified). This blocks live
censo pull/compare/apply and therefore positive censo-backed calendar enrolment.
Grounded in `2026-07-10-censo-g313-launcher-fix-research` and the P01 exec
record `2026-07-10-censo-g313-launcher-fix-P01-S01`.

## Considerations

- P01 established (authenticated capture): `MdcAcceso` is a 404; the session
  authenticates correctly (the operator's name renders in the sede chrome).
- There is no simple read-only "Mis datos censales" HTML endpoint. The real
  censal data is the prefilled Modelo 036 behind
  `www6.../wlpl/OVCT-CXEW/DialogoRepresentacion`, which renders "Selección del
  contribuyente a representar" (an *en nombre propio* chooser + CONFIRMAR), and
  only after that confirm does the ZK-framework (`.zul`) SPA load
  (`BU36-ASIS/M036/index.zul` personas físicas, `BU36-M036/MOD036/index.zul`
  general). The page carries `zul`/`zkau` markers, not `label:value` HTML.
- The current parser (`parse_g313_html` / `_G313_LABELS`) scrapes a flat
  `label:value` text projection — it cannot read a ZK component tree. The
  parser strategy must change, not just its labels.
- Only the operator can run the live path (single Cl@ve identity), so the ZK
  field structure and any representation-drive quirks must be captured under an
  authenticated session before the parser is re-grounded.

## Considered options

1. **Re-point the launcher to the representation-gated Modelo 036 ZUL, drive the
   *en nombre propio* confirm, and re-ground the parser to ZK-component
   extraction (chosen).** Targets the real AEAT censal surface P01 found. Larger
   than a wait-tweak but it is the only path that actually reaches the data.
2. **Wait for the es13 SPA on the existing `MdcAcceso` URL (original ADR
   thesis).** Rejected: falsified by P01 — the URL is a 404, so no amount of
   waiting reaches a censal page.
3. **Read the general 036 ZUL (`BU36-M036/MOD036/index.zul`) instead of the
   personas-físicas Censos-WEB (`BU36-ASIS`).** Held open: both sit behind the
   same representation gate; the capture in P02.S02 decides which yields the
   fields `CensoFactSet` needs with the least interaction.
4. **Drop live censo read entirely and source censal facts another way.**
   Rejected here: out of scope for a defect fix; a product-direction change
   would need its own ADR.

## Constraints

- Blocking precondition: an authenticated capture of the ZK censal page's
  component structure (identity redacted) is required before the parser is
  re-grounded — the label-scraping contract does not survive the ZK move.
- The representation gate requires driving a confirm interaction; the driver
  becomes an authenticated read-with-interaction, still fail-closed on off-AEAT
  navigation via the existing read guard.
- Live acceptance is operator-gated; the automated gate is a recorded-navigation
  regression through the existing `browser_session_factory` seam.

## Implementation

Re-point `censo_g313_launcher` (and add the representation `ref` target) in
`src/aeat/core/external_constants.toml` to the `OVCT-CXEW/DialogoRepresentacion`
flow. In `_censo_live.py`, after navigating to the representation gate, detect
and confirm the *en nombre propio* selection, wait for the ZK SPA to render the
censal panel (bounded by `aeat_browser_selector_probe_timeout_ms`), then capture
the rendered DOM. Replace the flat `label:value` parse in `_censo.py` with a
ZK-component extraction grounded on the captured field structure, preserving the
typed `CensoFactSet` output contract and the `CensoParseError`-on-shape-change
discipline. Keep the fail-closed read-guard re-assertion on every landing URL.

## Rationale

Option 1 is the only approach that reaches the real censal data P01 located; the
original wait-for-SPA thesis is dead because the configured URL 404s. Re-pointing
to the representation-gated 036 ZUL plus a component-aware parser is a larger
change than first scoped, but P01's capture-first gate is exactly what surfaced
this before any wait-tweak code was written. The typed `CensoFactSet` boundary
and the CLI/application layers are unchanged, so the blast radius stays inside
the outbound sede adapter and its constants.

## Consequences

- Gains: live censo pull returns a populated `CensoFactSet`, unblocking
  compare/apply and positive censo-backed calendar enrolment (the deferred
  positive direction of the reconciliation plan's S11).
- Honestly: this is a bigger lift than a URL swap — a representation-drive plus a
  parser rewrite from text-scraping to ZK-component extraction — and it cannot be
  fully validated without one operator-run live pull.
- Pitfall: ZK (`zkau`) SPAs render asynchronously and re-key component ids per
  session; the parser must anchor on stable field labels/roles within the
  component tree, not on generated ids, or it will be brittle.
- Risk to weigh: if the representation-drive or ZK extraction proves
  disproportionately fragile, option 4 (a product-direction change for censal
  facts) may deserve its own ADR rather than hardening a brittle scrape.

## Update 2026-07-10 — P02.S04 capture raises the option-4 question to a live decision

The P02.S04 authenticated capture (`2026-07-10-censo-g313-launcher-fix-P02-S04`)
drove the representation confirm and reached the ZK app `BU36-ASIS/M036/index.zul`
("Censos WEB"). It is a multi-step ZKoss tool whose landing is a MENU (Baja /
Modificación de datos / errores), not censal data — and the actual census fields
sit behind the prefilled **036 modification form** (further in-tool ZK steps).
None of the `_G313_LABELS` appear at any level reached. So reading census data
means operating AEAT's census **modification** tool through several fragile ZK
interactions, one accidental submit away from mutating AEAT census state — which
`aeat-safety-legal-gates` forbids. This materially raises the cost and risk of
option 1 and elevates the previously-reserved options to a real fork the operator
must decide before P02 code is written:

- **Option 1 (drive the modification tool to read):** reach the prefilled 036 via
  Censos WEB and extract fields read-only. Highest fidelity, but fragile and
  brushes the mutation surface; needs strict never-submit guards.
- **Option 3-variant (find a true read-only censal endpoint):** search AEAT for a
  consulta-only "datos censales" service (e.g. a different procedure/portal) that
  renders data without the modification tool. Not found in the empresarios censal
  hub during P01; needs a wider live search.
- **Option 4 (reconsider live censo read):** treat live censo enrolment as
  operator-manual (the taxpayer supplies censal facts) rather than scraped, and
  keep the calendar's `censo.enrolment_unverified` posture. Cheapest, safest, no
  modification-tool driving; loses the automated censo pull. Would need its own
  small ADR.

Decision deferred to the operator; P02 code is NOT started until this fork is
resolved.
