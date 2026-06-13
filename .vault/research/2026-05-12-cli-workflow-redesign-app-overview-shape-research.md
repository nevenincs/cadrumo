---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `app overview shape`

## Topic

Design the `aeat app overview` read surface for current workflow status,
deadline calendar, today view, backlog view, and deadline/modelo explanation.

## Audit Surface

The audit covered the apex CLI workflow redesign ADR, the bucket ADR,
the bucket-event-history ADR, current overview and deadlines CLI code,
`application/overview/`, `domain/deadlines/`, and current profile/read/output
helpers used by overview and deadlines commands.

## Rewrite Scope

This research supports a child ADR that locks the `aeat app overview` grammar,
absorbs legacy deadline/status/today/backlog concepts, retires root deadlines
and root status shapes, and removes legacy profile/output paths from the
redesigned overview surface.

## Summary

`aeat app overview` is the operational read surface over the active profile and
active bucket. It answers "what is due, what is blocked, and what should the
operator inspect next" without mutating storage and without becoming a bucket
maintenance surface.

The overview surface absorbs the historical `deadlines` and phantom `status`
families. It does not reintroduce root `aeat status`, root `aeat deadlines`, or
any `app bucket` command.

## Evidence Anchors

- The apex ADR requires `aeat deadlines` to move to `aeat app overview`.
- Apex §4.1 marks `aeat app overview` as the evolving home for `status`,
  `calendar`, `today`, and optional `backlog`.
- Apex §6 adopts the phantom `status show / today / resume / history / backlog`
  family as `app overview`, subject to child ADR decisions.
- The bucket ADR locks the redesigned roots to `aeat config` and `aeat app`,
  with `app` operating over active-bucket list/status views.
- The bucket-event-history ADR requires app status/list summaries to include
  material event context while keeping full event browsing under
  `aeat config bucket history`.
- Current `aeat app overview` only mounts `status`.
- Current `status --calendar` already builds typed calendar output from
  `application.overview`.
- `application/overview/` exposes typed calendar entries, warnings,
  completeness, and deadline status mappings.
- `domain/deadlines/_engine.py` is pure and registry-backed, but it does not
  apply festivo or business-day shifts.
- Legacy `entrypoints/cli/deadlines` exists but is not root-mounted.
- Legacy deadlines code reads `--profile` and `AEAT_DEFAULT_PROFILE_PATH`
  instead of active workflow/profile/bucket state.
- Current overview profile reading uses workflow state, but the interim mapping
  can silently default missing identity data.
- Legacy setup status still emits old setup-oriented next actions.

## Current Drift

- Live root still exposes legacy roots that the accepted redesign retires.
- `aeat app overview status --calendar` hides calendar behavior behind a flag
  even though the redesign requires a dedicated `calendar` verb.
- `today` and `backlog` are not implemented.
- `entrypoints/cli/deadlines` is dead public surface: code exists, but the root
  command is not mounted.
- Legacy deadlines commands use their own profile read path and Rich-only
  rendering.
- The redesigned overview surface must use `_emit`, active workflow/profile
  state, and active bucket state.

## Proposed Grammar

```text
aeat app overview status
    [--period PERIOD]
    [--verbose]
    [--format json|text]

aeat app overview calendar
    --from YYYY-MM-DD
    --to YYYY-MM-DD
    [--allow-incomplete]
    [--format json|text]

aeat app overview today
    [--date YYYY-MM-DD]
    [--allow-incomplete]
    [--format json|text]

aeat app overview backlog
    [--from YYYY-MM-DD]
    [--to YYYY-MM-DD]
    [--format json|text]

aeat app overview explain MODELO
    [--year YYYY]
    [--format json|text]
```

Migration mapping:

- `aeat deadlines list --year YYYY` becomes
  `aeat app overview calendar --from YYYY-01-01 --to YYYY-12-31`.
- `aeat deadlines next --year YYYY` becomes `aeat app overview today` with a
  `next_due` payload field.
- `aeat deadlines explain MODELO` becomes `aeat app overview explain MODELO`.
- Phantom `status show` becomes `aeat app overview status`.
- Phantom `status today` becomes `aeat app overview today`.
- Phantom `status history` is rejected here; use `aeat config bucket history`
  and `aeat app modelo history`.
- Phantom `status resume` is deferred to the workflow-resumption ADR.
- Phantom `backlog show/scaffold` becomes `aeat app overview backlog`.
- Backlog import/resume behavior is rejected unless later workflow ADRs create
  a real backend lifecycle for it.

## Output Contract

JSON output uses stable typed objects, not Rich-only rendering:

- `status`: active profile, bucket id, profile readiness, ledger summary,
  purchase-evidence summary, payable/collectible operation summary, draft
  summary, unreadable row summary, next actions, recent events.
- `calendar`: current `OverviewCalendar` shape with range, entries,
  generated-at, warnings, and completeness.
- `today`: date, due today, due soon, overdue, next due, blocking items, next
  actions, recent events.
- `backlog`: range, items, counts by kind, blockers, next actions, recent
  events.
- `explain`: modelo, year, applicability, rationale, and profile facts used.

## Profile Read Path Requirements

Redesigned overview commands read active workflow/profile state only, then the
active bucket once bucket storage is available.

They do not preserve `--profile PATH` or `AEAT_DEFAULT_PROFILE_PATH`.

The current `_profile_to_autonomo()` path is acceptable only as an interim
adapter. Readiness-sensitive views must not silently default missing identity
data.

## Event And History Implications

Overview commands are read-only and emit no bucket events for normal reads.

They summarize recent material events where the event backend exists, using
timestamp, event type, object type, object id or revision, actor/source, and
outcome/state.

Full event browsing stays at `aeat config bucket history`.

## Dependencies

- Festivos and business-day shift blocks production-grade calendar and today
  close-date behavior.
- Workflow resumption blocks any real overview `resume` grammar and richer
  backlog actions.
- Bucket/profile init and active bucket resolution are required before status,
  today, and backlog can be fully bucket-scoped.
- Event-history backend support is required before overview can include the
  required recent-event summaries.
