---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:63e5014acc336d8b0f57d03f344c101c996cacf485e8c08096dc582ad6e1b183'
related: []
---
# `tui-architecture` audit: `W08.P27.S377 Declarations workspace screens review`

## Scope

Independent review of the live S377 Declarations package, locale copy, tests, and S392 projection integration. The review traced the four declared destinations, injected action authority, declaration/revision/filing terminology and source axes, semantic handoffs and refusals, protected data, real localization, eighty-column geometry, focus and scroll ownership, architecture boundaries, and whether fixtures prove the application contract rather than a frontend-local shape.

## Findings

### filing-history-drops-the-lifecycle-authority | high | Open: a measured history can render as empty

S392 defines the filing-history zone count as filing rows plus sanitized lifecycle rows and names local lifecycle as one of that zone's canonical sources. `DeclarationsFilingHistoryScreen` renders only `projection.filings`; it never reads `projection.lifecycle`. Its empty decision is based solely on the filing DataTable. A coherent projection containing lifecycle facts but no filing records therefore has a non-zero measured filing-history zone while the route displays the generic empty state and none of its history. Current tests force `lifecycle=()` in every fixture, so this contradiction is invisible.

Render the sanitized lifecycle stream with localized kind and occurred-at meaning, or explicitly split it into a separately named route and revise the S392 count/source contract. Add a lifecycle-only compositor test that proves non-empty history and exact natural declaration coordinates without protected fact/work identities.

### modelo-workspace-route-does-not-open-modelo-workspace | medium | Open: the fourth destination loops back to the landing

`declarations.modelo_workspace` has no factory. When its handoff is absent it truthfully refuses, but when a declaration handoff exists `resolve_declarations_screen` returns `DeclarationsOverviewScreen`; it never invokes the handoff or mounts an existing Modelo workspace destination. Selecting that navigation row can therefore replace the landing with another landing under a target labelled Modelo workspace. The catalogue test asserts only the four destination strings and never resolves or exercises this route.

Make the destination an honest, typed bridge that first admits a visible declaration identity and then invokes the injected existing-Modelo-workspace handoff, or remove the standalone destination and keep the per-declaration handoff as the sole path. Add an end-to-end route-request test proving the resulting target is not another overview and that absent admission remains a visible refusal.

### history-rows-drop-distinguishing-application-facts | medium | Open: distinct revisions and filings can be visually identical

Revision rows show natural address, creation date only, and state while dropping `updated_at`, `is_current`, and `is_filed`. Filing rows drop `filed_at`. Two revisions created on the same day with the same state, or multiple same-address filing records with the same local/evidence state, can consequently have identical visible rows even though Enter invokes different protected identities. This is unsafe selection semantics for history routes and leaves current/filed meaning out of an application projection that already owns it.

Render sufficient application-owned chronology and current/filed status with localized labels to make each actionable row distinguishable without exposing raw ids. Add multi-row same-day and amended-filing fixtures that assert the visible distinction and exact semantic handoff after reordered presentation.

### tests-do-not-use-a-coherent-projection-or-pin-source-copy | low | Open: the main fixture cannot be emitted by the live S392 projector

The TUI fixture directly constructs a projection where the declaration says there is no current filing, the revision is verified rather than filed, yet a current filing record exists. S392 now refuses that cross-authority combination. Tests also assert only three localized titles and one single-row callback; they do not pin local-versus-AEAT axis copy, revision terminology, lifecycle copy, or all three handoff identities. The production locale catalogues are genuinely authored, so this is a proof gap rather than a demonstrated fallback defect.

Build the primary fixture through `project_declarations_workspace` from coherent authorities, retain deliberately impossible shapes only in refusal tests, and assert representative source-axis/history terminology in every locale plus declaration, revision, and filing callbacks.

## Positive findings

All three implemented screens consume only the injected immutable projection and use protected ids solely as semantic row keys and handoff identities; rendered cells use natural Modelo/year/period coordinates and localized state/evidence labels. Catalogue actions are validated against the canonical work-list, revision-list, and filing-record-list command keys. Unavailable zones and omitted handoffs surface explicit refusals. Focus restoration uses semantic identities, Escape dismisses only the child, eighty-column compositor checks show no horizontal overflow and one page scroll owner, and production modules import no adapters, CLI, repositories, readers, concrete controllers, filesystem or network facilities. No financial inputs, NIFs, source transaction ids, or full protected identities are rendered.

## Verification

All 31 focused application-plus-TUI tests passed. Ruff passed for the Declarations package. ty passed for the Declarations package. These green gates do not discharge the findings because the fixtures contain no lifecycle rows, no multi-row history collisions, and no exercised Modelo-workspace bridge.

## Recommendation

NO-CLOSE. Remediate the high false-empty/history omission and both medium route/actionability defects before marking S377 complete; close the low fixture and locale proof gap with the same adversarial tests.
