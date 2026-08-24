---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:b9f4f8cd17bdced78c62832626200a3f52d11cf3cf03323b2580cc99bfd905bb'
step_id: 'S28'
related:
  - '[[2026-08-24-deadline-window-revision-authority-plan]]'
---

# Prove M210 calculate and verify envelopes emit grounded qualified plazo notices and never claim an ungrounded tipo-28 offset

## Scope

- `src/cadrumo/application/modelo/tests/`

## Description

- Use Vaultspec RAG and exact-symbol confirmation to locate the sole result-disposition authority, filing-window matcher, EVENT selector matcher, and M210 notice path.
- Enrol Modelo 210's existing `cuota_diferencial` in the shared result-disposition specification for ingreso, cuota cero, and devolución.
- Route qualified concrete EVENT work to annual M210 windows inside the existing deadline matcher through `selector_period_matches_request`, preserving exact unqualified and non-M210 behavior.
- Reuse the same canonical selector matcher when admitting concrete EVENT work units against the registry's symbolic `EVENT-N` declaration.
- Exercise real `calculate_modelo_work_revision` results and real JSON `app modelo work verify` envelopes for ingreso codes 01 and 35, cuota cero, devolución, imputadas code 02, and tipo 28 silence.
- Assert exact notice cardinality, registry dates, identifiers, legal references, and source references at both transport boundaries.

## Outcome

Modelo 210 now derives its canonical result disposition from the computed signed cuota diferencial and resolves grounded qualified annual filing windows from both annual grouped-renta work and concrete event work. Calculate and verify envelopes carry exactly one matching notice for every grounded case and carry none for the ungrounded tipo-28 offset.

The final redeclaration audit found one result-disposition table, one filing-window resolver, and one EVENT-family selector matcher. Independent review approved the corrected implementation after the tests were upgraded from direct helper calls to real envelope boundaries.

## Notes

- Focused Ruff passed on every touched code and test file.
- Focused pytest passed 25 tests across core disposition, deadline resolution, real M210 calculate/verify envelopes, and the existing inmobiliaria end-to-end path.
- Concurrent peer commits captured the shared core disposition, work-unit selector reuse, and domain regression files while work was in progress; the remaining S28 envelope and matcher changes are recorded here without reverting peer work.
