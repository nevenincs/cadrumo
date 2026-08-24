---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:d9007177473ce54d49328d0b23e96ac0d5ecc4d38ad61f32f2c4db556643798d'
step_id: 'S13'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---
# Re-adjudicate Modelo 322 deadlines and materialise every officially evidenced periodic row

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/322/`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_322_registry.py`

## Description

- Lead with Vaultspec RAG discovery, then confirm exact symbols and call sites before editing.
- Re-adjudicate M322 monthly presentation windows against the bundled official AEAT calendars for 2022 through 2026.
- Materialise every officially evidenced monthly coordinate beneath the revision selected by `select_revision`.
- Preserve an absent payment cutoff because the available AEAT domiciliation authority does not explicitly list Modelo 322.
- Keep ejercicio 2026 period 12 absent because its physical filing deadline belongs to 2027 and no official 2027 calendar is enrolled.
- Close construct references over every authored deadline ID and calendar source.
- Add exact census, date, evidence, ownership, semantic-coordinate, and projection regression coverage.

## Outcome

M322 now has complete official-calendar coverage for all twelve months of 2022, 2023, 2024, and 2025, plus months 01 through 11 of 2026. Each authored coordinate has exactly one law-selected owner, uses a canonical monthly `Period`, retains no unsupported payment cutoff, and is reachable from its revision construct. The only residual is `(2026, "12")`: its deadline occurs in 2027, so authoring it before an enrolled official 2027 calendar would be an inference.

Step S13 is therefore intentionally re-opened rather than falsely completed. The registry data portion is committed in `74e493279f`; the exact regression test and lifecycle evidence are committed separately.

## Verification

- Ruff formatting and checks passed for `test_modelo_322_registry.py`.
- The focused M322 module produced 13 passing tests and two failures caused by unrelated concurrent dirty M303/M390 semantic-role constraint edits during bundled full-registry validation. The exact M322 facts, local validator, canonical ownership, source closure, and all non-global assertions passed.
- No broad gate was rerun after the parent requested lifecycle closure only.

## No-redeclaration audit

Vaultspec RAG semantic discovery located the existing `select_revision` authority, deadline ownership validator, `ValidatedRegistryAuthority.deadline_windows` projection, canonical `Period`/`registry_period_kind`, and `resolve_filing_window`. Exact `rg` confirmation found no M322-specific resolver, selector, period parser, cadence map, horizon, or deadline catalogue. This change adds registry facts and tests only; it introduces no code authority or duplicate algorithm.
