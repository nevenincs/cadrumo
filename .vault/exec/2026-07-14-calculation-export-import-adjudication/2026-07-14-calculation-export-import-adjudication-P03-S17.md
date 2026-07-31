---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
body_hash: 'sha256:e4e5108625b43f7a7fab3fd830aa0f20a468b6dd88b7c06d0d2d57338c8c1d0a'
step_id: 'S17'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---
# Confirm Modelo 200 submitted-file parsing as delivered through the generic export parser and gate declaration-PDF work on a real specimen

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200/`
- `src/cadrumo/adapters/inbound/declaracion/`
- `.vault/reference/`

## Description

Ground the two candidate surfaces independently with intent-first searches:

```text
vaultspec-rag search "Modelo 200 submitted file 2025 export layout parse_export_payload real round trip" --type code
vaultspec-rag search "Modelo 200 declaration PDF extraction profile sanitized filed specimen" --type code
vaultspec-rag search "Modelo 200 submitted file declaration PDF extraction evidence" --type vault --doc-type adr
```

The submitted-file query was noisy, so confirm that surface through the approved exact-source fallback. The declaration-PDF and directed ADR searches located the generic registry-profile parser and the accepted submitted-file-first live-capture decision.

Inspect the exact registry and parser boundaries with:

```text
Get-Content -Raw 'src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/revision.toml'
Get-Content -Raw 'src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0000-manifest.toml'
rg -n 'aeat-dr-200-2025' 'src/cadrumo/_data/registry/aeat/legal/is.toml'
rg -n 'parse_export_payload|submitted_file' 'src/cadrumo/adapters/outbound/aeat/sede/_declarations_observations.py'
fd -t d 'extraction_profiles' 'src/cadrumo/_data/registry/aeat/modelos/200'
rg -n '^def parse_declaracion_bytes|authority|snapshot|_select_extraction_profile' 'src/cadrumo/adapters/inbound/declaracion/_parser.py'
```

The revision starts at `2024-01-01`, but its only export layout is `modelo-200-fichero-boe`, sourced exclusively by `aeat-dr-200-2025`. That reviewed AEAT record design applies from `2025-01-01`; it does not establish a 2024 submitted-file layout. The live submitted-file path resolves the snapshot layout, passes the bytes to `parse_export_payload`, verifies filing context, and maps parsed casillas into observations. The Modelo 200 registry has no `extraction_profiles` directory. The generic declaration parser requires a registry snapshot with exactly one applicable `declaracion_pdf` profile, so a record design cannot substitute for a filed-PDF specimen or profile.

Run the bounded real-code verification anchors with:

```text
uv run pytest -q -o addopts='' 'src/cadrumo/domain/calculations/registry/tests/test_modelo_200_registry.py::test_modelo_200_page_014_export_binding_resolves_00562_to_liquidacion' 'src/cadrumo/domain/calculations/registry/tests/test_modelo_200_registry.py::test_modelo_200_liquidacion_014_014b_formulas_and_exports_use_segment_identities' 'src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part2.py::TestSubmittedFileObservation::test_redacted_submitted_file_values_become_observed_casillas' 'src/cadrumo/application/filing/tests/test_fichero_boe_export_roundtrip.py::test_export_roundtrip_preserves_every_covered_casilla' 'src/cadrumo/adapters/inbound/declaracion/tests/test_parser_boundary_m130.py::test_real_redacted_modelo_130_declaration_copy_extracts_partial_casillas'
```

## Outcome

### Audit-ready finding: Modelo 200 submitted-file parsing, exercise 2025

- **Candidate:** Modelo `200`; `submitted_file` parsing surface; annual period `0A`; exact evidenced exercise window `2025-01-01` through `2025-12-31`.
- **Mandate:** `proven`. The accepted live filing-data capture decision makes submitted-file parsing the preferred observation path where AEAT exposes the artefact, and the adjudication baseline requires reconciliation from available declaration evidence.
- **Exact authority window:** `aeat-dr-200-2025`, reviewed AEAT record design `DR200e25.xls`, applies from `2025-01-01`; registry layout `modelo-200-fichero-boe` is attached to revision `2024-y-siguientes`. Authority is exact for exercise 2025 only. The revision's `2024-01-01` start does not extend the 2025 layout backwards.
- **Canonical implementation state:** `delivered`. The generic live submitted-file route calls `resolve_export_layout(snapshot)`, passes the selected `modelo-200-fichero-boe` layout and bytes to `parse_export_payload`, validates declaration context, and converts parsed casillas into observations. No Modelo-specific submitted-file parser is missing.
- **Real evidence or specimen:** `available` for this implementation-state adjudication: the reviewed, hash-pinned AEAT 2025 record design and committed registry layout are present. Modelo 200 layout-resolution tests and real generic submitted-file observation and parser round-trip tests exercise the same production contracts. No separate real filed Modelo 200 submitted-file specimen was found, so this finding does not claim specimen-backed 2024 or 2025 field parity beyond the registered layout.
- **Retirement:** `false`.
- **Evidence block:** `false`; the delivered-equivalent decision needs no new specimen to authorize duplicate implementation work.
- **Four-condition gate:** `mandate_met=true`; `exact_authority_met=true`; `canonical_gap_met=false`; `eligible_met=true`.
- **Gate result:** `fail` because there is no canonical implementation gap.
- **Disposition:** `delivered-equivalent`.
- **Next action:** `none` for implementation. Preserve the generic submitted-file path and restrict the claim to exercise 2025 unless separate exact-window authority and evidence prove another exercise.

### Audit-ready finding: Modelo 200 declaration-PDF extraction, exercise 2025

- **Candidate:** Modelo `200`; `declaration_pdf` extraction surface; annual period `0A`; exact candidate exercise window `2025-01-01` through `2025-12-31`.
- **Mandate:** `proven`. The accepted live filing-data capture decision requires declaration-PDF parsing as the fallback observation path where a submitted file is unavailable, and reconciliation requires observations from available declaration evidence.
- **Exact authority window:** the reviewed `aeat-dr-200-2025` record design and `boe-modelo-200-2025-form` authority cover exercise 2025. They establish the filing window and form authority but do not prove printed declaration-PDF geometry. No 2024 declaration-PDF claim is made.
- **Canonical implementation state:** `gap`. The generic `parse_declaracion_bytes` engine exists, but the Modelo 200 revision contains no registry-owned `declaracion_pdf` extraction profile. The gap is profile data and real-behavior evidence, not a missing parser engine.
- **Real evidence or specimen:** `missing`. No real sanitized filed Modelo 200 declaration PDF for exercise 2025 is bundled. The 2025 record design and the 2024 manual cannot prove labels, coordinates, text-layer behavior, or form fields in filed PDF bytes.
- **Retirement:** `false`.
- **Evidence block:** `true`; the missing artefact is a real sanitized filed Modelo 200 declaration PDF for the exact exercise-2025 window, with enough stable printed geometry to support deterministic extraction and a real corpus test.
- **Four-condition gate:** `mandate_met=true`; `exact_authority_met=true`; `canonical_gap_met=true`; `eligible_met=false` because real filed-PDF evidence is unavailable.
- **Gate result:** `fail`.
- **Disposition:** `evidence-gated`.
- **Next action:** obtain and sanitize a real filed exercise-2025 declaration PDF. Only after that evidence exists may a successor proposal add reviewed profile data and real corpus coverage through `parse_declaracion_bytes`; do not derive a profile from `modelo-200-fichero-boe`, the 2024 manual, or synthetic geometry.

The two surfaces remain separate. Neither disposition authorizes production source, test, or registry changes.

## Notes

- All intent-first RAG searches completed. Exact-source inspection replaced the noisy submitted-file result rather than treating weak semantic retrieval as evidence.
- The absence of a Modelo 200 `extraction_profiles` directory was confirmed independently from the presence of the 2025 export-layout fragments.
- The bounded verification passed 7 collected tests in 45.79 seconds: two Modelo 200 layout-resolution tests, three parameterized generic export/parser round trips, one live submitted-file observation test, and one generic declaration-PDF parser test using a synthetic Modelo 130 fixture. Despite that test's `test_real_redacted_modelo_130_declaration_copy_extracts_partial_casillas` name, it is not evidence of a real redacted or filed PDF and does not reduce the Modelo 200 specimen gate.
- The existing Modelo 200 layout tests build a `filing_year=2024` snapshot because the layout sits under revision `2024-y-siguientes`. That proves current registry exposure, not official 2024 layout authority; this adjudication limits delivered-equivalent submitted-file support to exercise 2025.
- No 2024 submitted-file or declaration-PDF support is claimed from the 2025 layout authority.
- The P03.S17 plan checkbox remains open for parent review. Nothing was staged or committed.
