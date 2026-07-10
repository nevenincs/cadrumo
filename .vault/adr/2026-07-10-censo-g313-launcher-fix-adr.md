---
tags:
  - '#adr'
  - '#censo-g313-launcher-fix'
date: '2026-07-10'
modified: '2026-07-10'
related:
  - "[[2026-07-10-censo-g313-launcher-fix-research]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #adr) and one feature tag.
     Replace censo-g313-launcher-fix with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     Status convention: the H1 status value is one of proposed, accepted,
     rejected, superseded, or deprecated. A new ADR starts as proposed; it
     moves to accepted or rejected when the decision is made; it becomes
     superseded when a later ADR replaces it (set by vault adr supersede,
     which also records superseded_by); and deprecated when it is retired
     without a direct successor.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `censo-g313-launcher-fix` adr: `wait for es13 censal SPA before capturing G313 HTML` | (**status:** `proposed`)

## Problem Statement

The outbound G313 (Mis Datos Censales) driver captures page HTML on the AEAT
Acceso launcher page before the authenticated `es13` censal SPA has loaded, so
the parser sees no censal fields and the caller refuses with an empty
`CensoFactSet`. This blocks live censo pull/compare/apply and therefore
positive censo-backed calendar enrolment. Result of the
`2026-07-10-censo-g313-launcher-fix-research` grounding of the live failure
observed during the live-censo-calendar reconciliation sweep.

## Considerations

- The published, durable AEAT entry point is the Acceso launcher
  (`/wlpl/BUGC-JDIT/MdcAcceso`); the resolved es13 data URL may be session- or
  token-scoped and less stable.
- The driver already receives a valid authenticated storage state (auth is not
  the problem); it merely captures too early.
- The codebase already exposes `PLAYWRIGHT_WAIT_NETWORKIDLE` and
  `aeat_browser_selector_probe_timeout_ms`; sibling sede surfaces wait beyond
  bare `domcontentloaded`.
- Only the operator can run the live path, so the true `MdcAcceso`→es13
  transition shape and the es13 field labels must be confirmed against a
  captured authenticated page before any parser re-grounding is trusted.

## Considered options

1. **Wait for the es13 censal SPA before capture (chosen).** Keep the published
   Acceso entry point; after `goto(MdcAcceso)`, wait for a stable es13 content
   marker (or `networkidle`) bounded by the existing selector-probe timeout,
   then capture. Lowest-risk, most durable; matches sibling surfaces.
2. **Re-point the launcher at the resolved es13 data URL.** Rejected as the
   primary fix: the direct URL is likely session/token scoped and more brittle
   than the published Acceso entry; may still need the same post-nav wait.
3. **Explicitly follow/submit the Acceso dispatch.** Held in reserve: only
   needed if the transition is an active click/submit rather than a passive
   redirect — a fact the captured `MdcAcceso` HTML will decide.

## Constraints

- Blocking precondition: a captured authenticated `MdcAcceso`-then-es13
  HTML/trace (identity redacted) is required to (a) confirm whether the
  transition is a passive redirect or an active dispatch, and (b) re-ground the
  `_G313_LABELS` parser labels against the true es13 data page. The chosen
  option's exact wait target (marker selector vs networkidle) is confirmed by
  that capture; if the capture shows an active dispatch, option 3 is folded in.
- Live acceptance is operator-gated (single real Cl@ve identity); the automated
  gate is a recorded-navigation regression through the existing
  `browser_session_factory` seam.

## Implementation

Extend `fetch_g313_censo` / `_fetch_g313_censo_with_storage_state` in the
outbound sede driver so that, after navigating to the Acceso launcher, it waits
for the es13 censal content to materialise — a `page.wait_for_selector` on a
known es13 marker, falling back to `networkidle` — bounded by
`aeat_browser_selector_probe_timeout_ms`, before calling `page.content()`. The
read-guard re-assertion on the resolved landing URL is preserved (fail-closed on
off-AEAT redirects). If the captured page confirms an active access control,
add the dispatch step before the wait. Re-ground `_G313_LABELS` only if the
captured es13 page shows the parser's current labels have drifted. All changes
stay inside `src/aeat/adapters/outbound/aeat/sede/` and the launcher/marker
constants in `src/aeat/core/external_constants.toml`.

## Rationale

Option 1 keeps the durable published entry point and fixes the actual
defect — premature capture — with mechanisms the codebase already uses
elsewhere, minimising blast radius. It is grounded in
`2026-07-10-censo-g313-launcher-fix-research`: the captured `landing_path`
equalled the entry path and `censal_marker_present=false`, proving the SPA
redirect had not resolved at capture time. Re-pointing the URL (option 2) trades
a stable entry for a brittle one without addressing the timing, and an explicit
dispatch (option 3) is only justified if the capture proves the transition is
not a passive redirect.

## Consequences

- Gains: live censo pull returns a populated `CensoFactSet`, unblocking
  compare/apply and positive censo-backed calendar enrolment (the deferred
  positive direction of the reconciliation plan's S11).
- Honestly: the fix cannot be fully validated without one operator-run live
  pull, and the exact wait target and any parser-label re-grounding depend on a
  capture that does not yet exist — so the plan's first step produces that
  capture before code changes.
- Pitfall: an over-eager `networkidle` wait can hang on a chatty SPA; the
  bounded selector-probe timeout and a marker-first wait mitigate this.
- Opens: a reusable "wait for authenticated SPA content" shape other sede
  launcher surfaces can adopt if they show the same premature-capture risk.
