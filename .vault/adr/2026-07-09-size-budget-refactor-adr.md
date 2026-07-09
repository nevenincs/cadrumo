---
tags:
  - '#adr'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-09'
related: []
---

# `size-budget-refactor` adr: `Size-budget offender extraction approach` | (**status:** `accepted`)

## Problem Statement

`test_codebase_size_budgets.py` gates both a per-module and a per-callable
line-count ceiling. It went red on 12 offenders (6 modules, 6 callables)
that grew past their `_MODULE_LINE_LIMIT_OVERRIDES` /
`_CALLABLE_LINE_LIMIT_OVERRIDES` ratchet ceilings. Half the offenders sit in
files under active concurrent churn by other campaigns (prorrata, mcp); a
naive uniform fix would collide with in-flight peer work on those files.

## Considerations

- The gate's ceilings are already a per-file/per-callable ratchet, not a
  blanket default: an offender is one that broke through its OWN previously
  agreed override, not merely a large file.
- `full-tree-gate-must-distinguish-owner`: a shared, red, repository-wide
  gate must be triaged by ownership before any agent acts on it.
- `aeat-architecture-boundaries` and the existing per-domain module
  structure already establish the convention of splitting a grown module
  into a `_<parent>_<topic>.py` sibling behind the package's top-level
  facade, rather than a monolithic rewrite.

## Considered options

- **Fix all 12 offenders in one pass.** Rejected: 6 of the 12 sit in files
  the prorrata and mcp campaigns are actively editing; touching them now is
  a collision hazard, not a fix, and risks reverting or conflicting with
  in-flight peer commits.
- **Raise the ratchet ceilings instead of refactoring.** Rejected: the
  ceilings exist to catch exactly this growth; raising them papers over the
  signal rather than addressing the underlying module/callable cohesion.
- **Split owner-surface-stable offenders now via cohesive-chunk extraction
  into sibling modules; defer peer-owned offenders to their campaigns.**
  Chosen: matches the established per-domain module-splitting convention,
  touches no file under active peer churn, and leaves an honest
  green-except-peer gate state that a follow-up campaign closes.

## Constraints

- Every extraction preserves the public API and observable behavior
  exactly (a cohesive-chunk relocation, not a rewrite); no calculation,
  CLI, or storage semantics may change as a side effect.
- An owner-surface target must be re-confirmed peer-WIP-free via `git log`
  and `git diff` immediately before editing, since this is a shared,
  heavily concurrent worktree.
- A moved private symbol used by both the shrunk module and its new sibling
  is re-imported through the sibling (mirroring the existing
  `_calendar_models` / `_calendar_warnings` / `_coverage` pattern already
  established in `aeat.application.overview`), never duplicated.

## Implementation

For `application/overview/_calendar.py`: extract the calendar-event dedup
pair (`_calendar_event_sort_key`, `_dedupe_calendar_events`) and the entire
filing-evidence-reconciliation surface (`calendar_filing_evidence_from_sources`
and its private helpers, plus the three module-level evidence constants)
into a new sibling `_calendar_evidence.py`, following the same private
per-symbol import pattern the module already uses for `_calendar_models.py`
and `_calendar_warnings.py`. `_calendar.py` re-imports the symbols its
remaining code still calls, and re-exports the public
`calendar_filing_evidence_from_sources` symbol so the package `__init__.py`
facade is untouched. Within `build_overview_calendar`, the per-year
schedule computation and the per-obligation applicability-filtering loop
are each extracted into a private helper (`_schedules_for_calendar_range`,
`_entries_and_suppressed_from_schedules`), bringing the callable itself
under its override alongside the module.

For `_profiles.py:taxpayer_profile_from_mapping` and `secure_objects.py`,
the same cohesive-chunk extraction approach applies, executed by a parallel
agent under the same plan.

The 6 peer-owned offenders (`_iva_ledger.py` / `_classify_iva_transaction`,
`_ledger_bindings.py`, `_models.py`, `_ledger.py:ledger_add` -- prorrata;
`_commands.py`, `_server.py:build_server` / `_call_tool` -- mcp) are
recorded but not touched; they remain the owning campaigns' responsibility.

## Rationale

Splitting by ownership rather than fixing everything in one sweep follows
`aeat-swarm-orchestration`'s abort-if-WIP discipline: this worktree runs
many concurrent campaigns, and editing a file another campaign is actively
churning risks reverting or conflicting with in-flight work regardless of
how correct the size-budget fix itself is. Extracting a cohesive concern
into a sibling module (rather than restructuring in place) keeps the diff
reviewable and behavior-preserving, and matches the convention the
`overview` package already established with `_calendar_models.py` /
`_calendar_warnings.py` / `_coverage.py`.

## Consequences

The size-budget gate is expected to land green-except-the-6-deferred-
offenders once every owner-surface Phase closes -- an honest, documented
partial state rather than a false "campaign complete" claim. The deferred
6 remain a known, tracked gap until the prorrata and mcp campaigns land
their own extractions; `test_codebase_size_budgets.py` continues to fail
loudly on them in the interim, which is the correct and intended signal.
