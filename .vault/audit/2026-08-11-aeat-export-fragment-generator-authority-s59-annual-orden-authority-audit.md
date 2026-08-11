---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:095d0266ac216c43aba4493a11c3bc8cb6649a14771410e143775f786d40669d'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
---
# `aeat-export-fragment-generator-authority` audit: `S59 annual Orden authority formal review`

## Scope

Final formal review of `W04.P07.S59` against the accepted annual-Orden amendment, the plan acceptance text, and candidate `5e3d11a0ba180ff547dcfc66997a47a0bd0ab381`. The review covered the annual source compiler, immutable projection and reference coordinates, registry snapshot integration, strict source-sidecar validation, formula scope handling, filing value arrival, constructor propagation, all direct runtime callers, legacy deletion, and exact revision-source authority.

Verdict: **PASS**. Luna approved candidate `5e3d11a0ba180ff547dcfc66997a47a0bd0ab381`; no open critical, high, medium, or low S59 finding remains.

## Findings

### filing-builder-and-import-callers-omitted-scope | critical | Resolved: every caller states the closed decision

`build_draft` requires `m303_regimen_simplificado_scope` with no default and passes the value unchanged to `calculate_registry_snapshot`. Its production and test callers, including import and generic filing boundaries, were migrated explicitly. Modelo 303 callers pass the intentional typed decision; scope-unaware and non-303 boundaries pass `None` and therefore retain the runtime's fail-closed modelo check. No profile inference, optional tunnel, compatibility default, or legacy overload remains.

### annual-orden-constructor-propagation-incomplete | high | Resolved: canonical coordinates reach every production constructor

The annual-Orden projection and references require `orden_id`, ejercicio, registry revision, canonical source, content digest, and `cuota_minima_pct`. Constructor census coverage proves production compilation supplies these coordinates and the bundled 2026 authority resolves the pinned identifier and statutory percentage rather than recreating a test-only row.

### sidecar-metadata-was-under-validated | high | Resolved: the paired extraction authority is exact

The loader accepts only the closed top-level and unit schemas and validates schema version, source kind, status, canonical source path, digest, preprocessor identity, and attribution. Copied-real-sidecar mutation tests refuse unknown keys, missing required metadata, stale content, and JSON-versus-Markdown divergence. The sidecar proof lane contains 31 passing tests.

### registry-runtime-default-and-caller-omissions | critical | Resolved: all 248 direct calls are explicit

`calculate_registry_snapshot` requires `m303_regimen_simplificado_scope`; signature binding proves omission raises `TypeError`. The all-source AST ratchet enumerates 248 direct calls with zero omissions: non-303 or generic calls state `None`, while M303 execution paths use the typed `REGIMEN_SIMPLIFICADO_NOT_CLAIMED` or `REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED` decision. Only the dedicated missing-scope refusal test passes `None` to an M303 snapshot. Not-claimed stays neutral, rejects simplified rows, and evidence-required refuses pending S58.

### revision-source-assertion-dropped-annual-authority | high | Resolved: both authorities are exact and distinct

Every explicit Modelo 303 revision now asserts the complete ordered source tuple: one revision-specific active record-design source, official procedure guidance, exactly one filing-year-pinned annual Orden source, and the base-form authority. Both 2024 design epochs intentionally share the same 2024 annual Orden, while their record-design sources remain distinct. The assertion is exact rather than subset-based and the source slice passes five tests.

### parallel-selector-and-runtime-inference | high | Resolved: one private selector remains behind the canonical resolver

The former public selector, parallel coefficient tables, test-only rows, raw-IAE selection, and runtime formula-operation inference are deleted. `_select_m303_annual_orden_projection` is private to `resolve_m303_regimen_simplificado_snapshot`; formula evaluation consumes the resolved immutable snapshot.

## Recommendations

S59 is complete. Preserve the required no-default scope boundary, the 248-call ratchet, the exact annual-source coordinate, and the explicit S58 evidence refusal. S55 remains the owner of secure-profile composition and mapping; S58 remains the owner of evidence-bearing applicability.

Final evidence: the S59 lane passed 74 tests; `test_formula_runtime.py` passed 9; the engine and all-source ratchet passed 17; strict sidecar coverage passed 31; and the exact M303 source slice passed 5. The annual-Orden generator check, full registry verification, and scoped Ruff all passed. Detached-base comparison proved zero introduced `ty` or basedpyright diagnostics.

Separate campaign priorities remain honestly open and are not claimed green by S59: four pre-existing deduction-authority fixtures, sixteen Renta tarifa failures missing `renta-2024-profile-deduccion-maternidad`, one record-design value drift from `0` to `0000`, and stale submitted-file fixtures for withdrawn exports or invalid historical XML. None was masked with legacy compatibility.
