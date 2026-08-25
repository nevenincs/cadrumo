---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:b538ef7984d942e8421d7d9992f552a72fd2036fd4bd6dac4bc8e1bce8af010a'
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

M322 now has all twelve monthly deadline coordinates for every supported filing year 2022-2026. The final `(2026, "12")` coordinate is authored beneath `2026-y-siguientes`, opens 2027-01-01, closes 2027-02-01, and carries the 2027-01-27 payment cutoff through the official M303 procedure's explicit M322/M353 deadline parity and M322's governing legal source.

Every authored coordinate has one `select_revision` owner, canonical `Period` identity, construct membership, and closed source references. The focused repaired-model and deadline-engine run passes 164 tests. Step `W02.P04.S13` is complete.

## Verification

- Ruff formatting and checks passed for `test_modelo_322_registry.py`.
- The focused M322 module produced 13 passing tests and two failures caused by unrelated concurrent dirty M303/M390 semantic-role constraint edits during bundled full-registry validation. The exact M322 facts, local validator, canonical ownership, source closure, and all non-global assertions passed.
- No broad gate was rerun after the parent requested lifecycle closure only.

## No-redeclaration audit

Vaultspec RAG semantic discovery located the existing `select_revision` authority, deadline ownership validator, `ValidatedRegistryAuthority.deadline_windows` projection, canonical `Period`/`registry_period_kind`, and `resolve_filing_window`. Exact `rg` confirmation found no M322-specific resolver, selector, period parser, cadence map, horizon, or deadline catalogue. This change adds registry facts and tests only; it introduces no code authority or duplicate algorithm.
