---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:e3f465fcdb3afed770028d3b1c138b85d2468302c178c4fca769a08fb1b8fbab'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
---
# `aeat-export-fragment-generator-authority` audit: `S59 annual Orden authority formal review`

## Scope

Formal re-review of `W04.P07.S59` against the accepted annual-Orden amendment and plan acceptance text after remediation. The review covered `ActividadOrdenAnualId`, `ActividadOrdenAnualRef`, the immutable year/revision/source-digest projection and snapshot, source and generated-manifest loading, registry catalogue and snapshot integration, formula scope handling, filing projection, generated data, and the current focused tests.

Verdict: **PASS**. No open critical, high, medium, or low finding remains.

## Findings

### filing-builder-missing-applicability-authority | critical | Resolved: the public builder threads the closed scope decision

`build_draft` requires the typed `m303_regimen_simplificado_scope` argument and passes it unchanged to `calculate_registry_snapshot`. Modelo 303 calculations require the closed input, non-303 calculations reject a non-null value, not-claimed scope stays neutral, and evidence-required scope refuses pending S58. S59 has no secure-profile assembler or regime-composition enum; S55 owns that later mapping atomically.

### parallel-selector-and-runtime-inference | high | Resolved: one private selector is owned by the canonical snapshot resolver

The prior public `select_m303_annual_orden_projection` surface is absent from source and the registry facade. `_select_m303_annual_orden_projection` is private and called only inside `resolve_m303_regimen_simplificado_snapshot`. Formula evaluation no longer scans formula operations or selects an annual projection; it enforces the already-resolved closed scope and general-scope input neutrality. Filing projection consumes the resolved snapshot and no longer reselects the newest record-design source.

### snapshot-reference-coordinate-not-validated | high | Resolved: every activity reference is bound to the exact snapshot coordinate

`M303AnnualOrdenSnapshot` now owns ejercicio, revision, source, and content digest and validates every `ActividadOrdenAnualRef` against that complete coordinate in addition to ordered `orden_id` parity. It also verifies that each activity matches the filing year and cites the selected source. A dedicated mutation test changes revision and digest and proves strict refusal.

### markdown-sidecar-divergence-not-checked | medium | Resolved: JSON and Markdown sidecars are validated as one deterministic pair

The annual-Orden loader reconstructs the Markdown sidecar from the validated JSON units and requires exact equality with the committed `.extracted.md` member before accepting the source. A real copied-source mutation test corrupts the Markdown member and proves `sidecar pair diverges` refusal.

## Recommendations

No S59 remediation remains. Preserve the private-selector boundary, the required explicit scope input, and the explicit S58 refusal. S55 must add profile composition and mapping atomically rather than retrofitting a default or compatibility path.

Verification evidence: semantic RAG discovery reached the repaired implementation and governing ADR/plan records. The isolated candidate passed 25 annual-authority and engine tests plus 2 real `build_draft` boundary tests. `uv run --no-sync aeat app registry verify` passed with 73 modelos, 94 revisions, 798 legal references, 316 source references, 16800 casillas, and 1385 formulas. `uv run --no-sync python dev/registry/m303_orden_anual.py --check` passed. Scoped Ruff passed. A structural search found no public `select_m303_annual_orden_projection` declaration, import, export, or caller.
