---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S62'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Bind command-help invocations to `aeat` and product copy to CADRUMO while preserving AEAT counterparty language

## Scope

- `src/cadrumo entrypoint help authorities`

## Description

- Normalize stale `cadrumo` command prefixes to the canonical `aeat` executable
  at both live rendering and locale-maintenance boundaries.
- Normalize title-case product prose to the canonical `CADRUMO` display name
  without changing lowercase package and MCP identifiers.
- Preserve `AEAT` wherever locale prose names the Spanish tax authority.
- Exercise direct production rendering, folded YAML roundtrips, locale parity,
  catalogue audits, and isolated live help behavior.

## Outcome

The shared translation renderer now projects the binding identity while the
per-language catalogue migration remains open: title-case product copy renders
as `CADRUMO`, and stale command-leading `cadrumo` tokens render as `aeat`.
The matcher covers the command forms found in the catalogues, including folded
line breaks and `manual` guidance, without rewriting the `cadrumo` distribution,
`cadrumo-mcp`, `cadrumo://`, `CADRUMO_*`, or `AEAT`.

The locale manager and its developer command apply the same referent-aware
normalization when later Steps update catalogue leaves. No locale catalogue was
modified in this Step. All 34 focused renderer and parity tests passed, both
read-only locale catalogue gates reported every language healthy, scoped Ruff
passed, and an isolated real `aeat --help` rendered `CADRUMO`, retained `AEAT`,
used `aeat <comando> --help`, and exposed no title-case product name or
`cadrumo <comando>` guidance.

## Notes

The English, Spanish, Catalan, and Hungarian catalogue bytes intentionally still
contain stale product display and command copy. Steps S63 through S66 own those
mutations through the locale CLI, and S67 owns the resulting scaffold/parity
regeneration proof.

The first locale CLI probe inherited a local retired-state database and correctly
refused it; rerunning the same read-only gates with a fresh isolated CADRUMO state
root passed. The first PowerShell live-help assertion used case-insensitive
matching and therefore mistook `CADRUMO` for title-case `Cadrumo`; the corrected
case-sensitive assertion passed against the unchanged live output. No failure
was hidden or converted to a skip.
