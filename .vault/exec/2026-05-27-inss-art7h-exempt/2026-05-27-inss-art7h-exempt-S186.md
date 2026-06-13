---
step_id: "S186"
tags:
  - "#exec"
  - "#inss-art7h-exempt"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-27-inss-art7h-exempt-S186]]"
---

# inss-art7h-exempt S186

## Step

Implement INSS baja maternidad/paternidad prestaciones as IRPF-exempt under
Art. 7.h LIRPF. Previously casilla 0003 accepted total annual income without
distinguishing empleador rendimiento (tributable) from INSS prestacion
(exempt), causing ~€2,034.91 overpayment per Yara-shape case.

## Outcome

Commit `5733066cc` on branch `chore/eliminate-shims`.

## Deliverables

Registry (2024):
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/2064-0058-inss-exenta.toml` — casilla 0058, semantic_role `irpf_rendimiento_trabajo_prestacion_inss_maternidad_paternidad_exenta`, legal_refs `ley-35-2006:art-7-h`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0069-renta-2024-trabajo-total-ingresos-integros-computables.toml` — added `negate(0058)` to sum expression + `ley-35-2006:art-7-h` to legal_refs
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/completeness-manifest.toml` — entry for `0058`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/constructs/0009-renta-2024-mini-model-trabajo.toml` — `ley-35-2006:art-7-h` + `aeat-dr-100-2024-dictionary` added

Registry (2025):
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/2236-0059-inss-exenta.toml` — casilla 0059 (0058 is artistic activities in 2025), same semantic_role
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/formulas/0051-renta-2025-trabajo-total-ingresos-integros-computables.toml` — added `negate(0059)` only (0058 is not INSS exempt in 2025)
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/completeness-manifest.toml` — entry for `0059`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/constructs/0008-renta-work-income.toml` — `ley-35-2006:art-7-h` added

Legal corpus:
- `src/aeat/_data/registry/aeat/legal/irpf.toml` — `ley-35-2006:art-7-h` entry (committed in prior session)
- `src/aeat/_data/corpus/normatives/ley-35-2006.json` — art-7 article entry added

CLI:
- `src/aeat/entrypoints/cli/_modelo.py` — `--prestacion-inss-exenta IMPORTE` flag; resolved via `semantic_role` lookup at runtime; wired into `casilla_inputs` before engine run

Locales:
- `src/aeat/locales/es.yml` / `en.yml` / `ca.yml` / `hu.yml` — `prestacion_inss_exenta_help`, `prestacion_inss_exenta_not_decimal`, `prestacion_inss_exenta_casilla_not_found` keys

Tests:
- `src/aeat/domain/calculations/registry/test_inss_maternidad_paternidad_art7h.py` — 9 structural oracle tests; all pass

## Code Review

Standing gate review (G1–G6) passed:
- G1: No naked env reads. CLI wiring uses `tr()` and typed parameters.
- G2: Typed pydantic at boundaries. CLI `str | None` parsed to `Decimal`.
- G3: All user-facing error messages use `tr()` with locale keys.
- G4: Locale keys added via scaffold+audit pipeline, not hand-edited structure.
- G5: No shims, no re-exports, no duplication.
- G6: Tests verify structural properties (formula negate-expression tree, casilla semantic_role, legal_refs) against registry TOML — not tautological engine roundtrips.

Critical bug caught and fixed in review: the 2025 formula initially negated both
`0058` and `0059`. In the 2025 revision `0058` is the artistic activities
reduction (a different casilla), not the INSS exempt casilla. Removed the
stale `negate(0058)` from the 2025 formula; only `negate(0059)` remains.
