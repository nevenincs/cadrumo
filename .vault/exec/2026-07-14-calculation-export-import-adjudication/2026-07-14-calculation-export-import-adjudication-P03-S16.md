---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
body_hash: 'sha256:6bb16a947caf3b6410db7e7ee01b1a87031459b19bf10b2f21cec12ac541e991'
step_id: 'S16'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---
# Record Modelo 037 extraction as retired and preserve the active Modelo 036 successor boundary

## Scope

- `src/cadrumo/_data/registry/aeat/`
- `.vault/reference/`

## Description

Ground the candidate in current code and accepted decisions with intent-first searches:

```text
vaultspec-rag search "Modelo 037 declaration extraction retirement and Modelo 036 active successor boundary" --type code
vaultspec-rag search "Modelo 037 retirement Modelo 036 successor declaration extraction" --type vault --doc-type adr
```

The code search returned the active Modelo 036 lifecycle, censo ownership boundary, retired `M037` taxonomy, committed 036 registry data, and real registry tests. The directed ADR search returned the accepted Modelo 036/037 foundation decision and declaration-extraction architecture decision.

Confirm the exact registry, authority, parser, and test boundaries with:

```text
fd -t d '^(036|037)$' 'src/cadrumo/_data/registry/aeat/modelos'
rg -n "037|036|HISTORICAL_METADATA|superseded_by|active_work_unit_allowed|is_active_censo_modelo|censo_modelo_ownership" 'src/cadrumo/domain/calculations/registry/_censo_modelos.py' 'src/cadrumo/core/_modelo.py' 'src/cadrumo/domain/calculations/registry/tests/test_censo_modelo_foundation.py'
rg -n "modelo-036-declaracion-pdf|2025-02-03|boe-modelo-037-historical-suppression|BOE-A-2025-410" 'src/cadrumo/_data/registry/aeat/modelos/036' 'src/cadrumo/_data/registry/aeat/legal/censo.toml'
rg -n "^def parse_declaracion_bytes|authority|snapshot|_select_extraction_profile" 'src/cadrumo/adapters/inbound/declaracion/_parser.py'
```

Exact inspection found only the `036` registry directory. `NON_REGISTRY_MODELOS` includes retired `M037`, and `ValidatedRegistryAuthority.validate_modelo("037")` is required to fail. `censo_modelo_ownership("037")` proves the reviewed suppression source, returns historical metadata with no event kinds, forbids active work units, and names `036` as successor. The generic declaration parser requires a loadable registry snapshot and one applicable registry-owned extraction profile, so it cannot and must not manufacture a 037 path.

Run the bounded real-registry verification without the project's parallel pytest defaults:

```text
uv run pytest -q -o addopts='' 'src/cadrumo/domain/calculations/registry/tests/test_censo_modelo_foundation.py::test_modelo_036_is_active_event_triggered_foundation' 'src/cadrumo/domain/calculations/registry/tests/test_censo_modelo_foundation.py::test_modelo_037_is_historical_metadata_superseded_by_036' 'src/cadrumo/domain/calculations/registry/tests/test_censo_modelo_foundation.py::test_historical_037_contract_is_proven_by_registry_absence_and_suppression_source' 'src/cadrumo/domain/calculations/registry/tests/test_censo_modelo_foundation.py::test_resolve_censo_modelo_work_unit_foundation_rejects_historical_037' 'src/cadrumo/core/tests/test_modelo.py::test_modelo_registry_backed_members_match_registry' 'src/cadrumo/core/tests/test_modelo.py::test_non_registry_modelos_are_not_registry_loadable' 'src/cadrumo/domain/calculations/registry/tests/test_modelo_036_registry.py::test_modelo_036_revision_starts_at_2025_02_03' 'src/cadrumo/domain/calculations/registry/tests/test_modelo_036_registry.py::test_modelo_036_declaration_pdf_profile_legal_refs_match_target_casillas'
```

## Outcome

### Audit-ready finding: Modelo 037 declaration-PDF extraction, active window

- **Candidate:** Modelo `037`; `declaration_pdf` extraction surface; active-support window `2025-02-03` through open end. Historical pre-suppression artefacts are outside this current-support candidate and do not authorize an active profile.
- **Mandate:** `absent`. The accepted Modelo 036/037 foundation decision requires 037 to remain historical, inactive metadata and explicitly forbids an active 037 shim. It requires Modelo 036 to own the active successor surface.
- **Exact authority window:** Orden HAC/1526/2024, article 1 and final provision, document `BOE-A-2025-410`; published `2025-01-09`; effective `2025-02-03`; open-ended for this adjudication. The reviewed `boe-modelo-037-historical-suppression` source applies from the same date. Exact-window coverage is present for suppression, not for an active 037 extraction capability.
- **Canonical implementation state:** `delivered`. The required retirement/refusal behavior exists: 037 has no registry definition, cannot produce a registry snapshot or extraction profile, is classified as historical metadata, rejects active work units, and is superseded by the active registry-backed Modelo 036 boundary. The generic `parse_declaracion_bytes` path remains unchanged and registry-driven.
- **Real evidence or specimen:** `not-required` for an active 037 extraction claim because the accepted authority retires that surface. The reviewed BOE suppression source is available and applicable. No 036 record design, synthetic fixture, or historical 037 declaration may be repurposed to create a 037 profile.
- **Retirement:** `true`. Basis: Orden HAC/1526/2024 and the accepted Modelo 036/037 foundation ADR suppress active Modelo 037 from `2025-02-03` and name Modelo 036 as successor.
- **Evidence block:** `false`. No missing specimen blocks this decision; retirement independently closes the candidate. Missing evidence must not be converted into a reason to revive 037.
- **Four-condition gate:** `mandate_met=false`; `exact_authority_met=true`; `canonical_gap_met=false`; `eligible_met=false` because the candidate is retired.
- **Gate result:** `fail`.
- **Disposition:** `retired`.
- **Next action:** `none`. Preserve Modelo 036 as the active successor, keep 037 outside the registry, and do not add a 037 extraction profile, parser, shim, or active entry point.

The candidate is closed to implementation. No production source, tests, registry data, shared Reference, or shared audit changed.

## Notes

- Both intent-first RAG searches completed successfully. The code search completed in approximately 4 seconds; the directed ADR search completed in approximately 17 seconds. No semantic-search fallback was required.
- Direct real-test anchors are `test_modelo_037_is_historical_metadata_superseded_by_036`, `test_historical_037_contract_is_proven_by_registry_absence_and_suppression_source`, `test_resolve_censo_modelo_work_unit_foundation_rejects_historical_037`, `test_modelo_registry_backed_members_match_registry`, and `test_non_registry_modelos_are_not_registry_loadable`.
- An initial bounded pytest invocation used `-p no:xdist`, but project `addopts` still supplied `-n --dist=loadfile`; pytest rejected those arguments because the plugin had been disabled. This invocation produced no test result and is not counted as verification.
- The corrected bounded invocation passed all 8 selected real-registry tests in 44.98 seconds.
- The bounded status review showed unrelated in-flight production and test changes already present in the shared worktree. This Step did not edit them.
- The P03.S16 plan checkbox remains open for parent review. Nothing was staged or committed.
