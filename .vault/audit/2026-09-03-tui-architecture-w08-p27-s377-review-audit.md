---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:b985bd8ff9f605ebd27bd7e5c30377f04153073d863553acde1c2d24f70ab514'
related: []
---
# `tui-architecture` audit: `W08.P27.S377 Declarations workspace screens review`

## Scope

Independent review of the live S377 Declarations package, locale copy, tests, and S392 projection integration. The review traced the four declared destinations, injected action authority, declaration/revision/filing terminology and source axes, semantic handoffs and refusals, protected data, real localization, eighty-column geometry, focus and scroll ownership, architecture boundaries, and whether fixtures prove the application contract rather than a frontend-local shape.

## Findings

### filing-history-drops-the-lifecycle-authority | high | Closed: filing and lifecycle facts share one truthful chronological history

The initial filing-history screen ignored `projection.lifecycle` and could render a measured non-empty history as empty. Remediation merges filings and sanitized lifecycle facts by canonical occurrence time, renders localized lifecycle meaning at the natural declaration address, uses disjoint semantic row-key namespaces, and bases emptiness on the combined table. A lifecycle-bearing coherent S392 projection proves the table count equals the zone count and that protected lifecycle identities and private payload text are not rendered. This finding is closed.

### modelo-workspace-route-does-not-open-modelo-workspace | medium | Closed: the fourth route now launches the exact injected child

The initial fourth route returned another overview. Remediation introduces a distinct launcher screen and a narrow injected `ModeloWorkspaceScreenFactoryV1`. Selecting a visible declaration passes the exact projected row to that factory, pushes the returned host-neutral child, and restores the same semantic declaration row after dismissal. Missing factory or unavailable source still yields a visible refusal refusal. The compositor test proves the full selection, child, return, and focus path. This finding is closed.

### history-rows-drop-distinguishing-application-facts | medium | Closed: minute-bearing chronology and state axes distinguish same-day rows

The initial history screens truncated timestamps to calendar dates and omitted revision current/filed state. Remediation renders deterministic UTC date-and-minute timestamps, revision current/filed flags, and the independent filing status/evidence axes. The coherent fixture now contains two same-address draft revisions on the same day with identical state flags but different times; their visible rows are distinct, selecting the later row invokes its exact semantic revision, and no protected identity is displayed. Filing chronology uses the same formatter. This finding is closed.

### tests-do-not-use-a-coherent-projection-or-pin-source-copy | low | Closed: tests now consume S392 and pin source-axis semantics

The primary fixture now builds canonical work, revision, filing, evidence, and lifecycle authorities through `project_declarations_workspace`. All four locales assert authored landing, revision, filing-history, local-versus-AEAT axis, and lifecycle terminology while preserving the same semantic row keys. This finding is closed.

## Positive findings

All implemented screens consume only the injected immutable projection and use protected ids solely as semantic row keys and handoff identities; rendered cells use natural Modelo/year/period coordinates and localized state/evidence labels. Catalogue actions are validated against the canonical work-list, revision-list, and filing-record-list command keys. Unavailable zones and omitted handoffs surface explicit refusals. Focus restoration uses semantic identities, Escape dismisses only the child, eighty-column compositor checks show no horizontal overflow and one page scroll owner, and production modules import no adapters, CLI, repositories, readers, concrete controllers, filesystem or network facilities. No financial inputs, NIFs, source transaction ids, or full protected identities are rendered.

## Verification

Initial gates: 31 focused application-plus-TUI tests passed; Ruff and ty passed. Final remediation gates: all 16 focused TUI tests passed; Ruff and ty passed for the package. The final same-day probe confirms two otherwise equal draft rows render as `03/09/2026 09:15 UTC` and `03/09/2026 09:45 UTC`, and the selected later row reaches the exact typed handoff.

## Recommendation

CLOSE. All recorded high, medium, and low findings are closed. W08.P27.S377 is safe to mark complete.
