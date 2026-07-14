---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-07-12'
modified: '2026-07-12'
related:
  - "[[2026-05-03-calculation-truth-registry-rebuild-plan]]"
---

# `calculation-truth-registry` audit: `legacy rebuild plan tracking audit`

## Scope

Check whether the accepted calculation-truth-registry rebuild plan can be used
as a truthful execution tracker after the broader reconciliation pass. This is
a Vault tracking audit only; no calculation, legal registry, or test code is
changed.

## Findings

### legacy-plan-parser-gap | high | The approved rebuild plan contains 705 open checkboxes but reports 0/0 executable steps

The current plan is authorized by the accepted central-registry ADR and retains
substantial real implementation obligations. Its historical checklist syntax is
not canonical Vault `Wxx.Pxx.Sxx` structure, however: a direct scan finds 705
unchecked entries while `vault plan status` reports zero waves, phases, and
steps. The displayed 0/0 completion is therefore a parser limitation, not
completion or a reliable backlog measurement.

### continuation-needs-canonical-writing | info | The next safe move is a new structured continuation plan, not bulk checkbox closure

The accepted ADR remains sufficient authority for the registry direction, but
the old omnibus plan mixes completed historical work with genuine remaining
legal-data, fixture, revision, and verification work. A writer-led continuation
plan must re-ground each candidate against current registry source and existing
exec/audit evidence, then create canonical, independently executable steps.
No legacy checkbox is closed by this audit.

## Recommendations

- Use the Vault plan-writing workflow under the accepted registry ADR to create
  a canonical continuation plan with only the current residual work.
- Keep the legacy rebuild document as historical authority/evidence until that
  continuation plan has reconciled its rows; do not use its 0/0 parser output
  for progress reporting.
