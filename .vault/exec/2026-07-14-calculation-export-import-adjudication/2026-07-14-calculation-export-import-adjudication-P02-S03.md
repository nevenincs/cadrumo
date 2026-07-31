---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-17'
body_hash: 'sha256:3f842290233a433921db237ced2a1d764a07e7785f816134c9ea7ece7c0162d3'
step_id: 'S03'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---

# Adjudicate Modelo 036 outbound machine-file generation against the definitive current design and retire provisional-layout inferences

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/036/`
- `.vault/reference/`

## Description

- Read the accepted backlog-admission ADR, research, Reference, parent plan,
  rolling-audit contract, and exec-step template before adjudicating the
  candidate.
- Run `uv run vaultspec-rag search 'Modelo 036 outbound machine-file generation
  definitive v43 2025-02-03 export layout' --type code --limit 12`; confirm that
  current export ownership is the registry-driven `export_draft` path rather
  than a Modelo-specific Python format.
- Inspect the complete Modelo 036 registry tree and confirm that revision
  `2025-02-03-y-siguientes` starts on `2025-02-03`, has no `valid_to`, cites
  `aeat-dr-036-2025`, and declares no `export` or `export_layouts` fragment.
- Inspect `sources."aeat-dr-036-2025"` in
  `src/cadrumo/_data/registry/aeat/legal/censo.toml` and the bundled Modelo 036
  corpus manifest. Confirm that the registered source is definitive
  `DR036v43.xlsx`, SHA-256
  `791479fbf9e905faf1e43fa0bfbff974d5edaf85d198495892fa8446a1da2ebd`,
  126664 bytes, applicable from `2025-02-03` with an open end.
- Compare the definitive v43 extracted design with the separately bundled
  `DR036v42.xlsx`; retain v42 only as the manifest-labelled `PROVISIONAL`
  artefact and do not infer layout authority from it.
- Confirm the generic current path at `resolve_export_layout`, `export_draft`,
  `_render_export_layout`, and `parse_export_payload`. Confirm that
  `resolve_export_layout` rejects a revision with no exports and `export_draft`
  refuses a snapshot with no export-layout ids.
- Search the real export tests and Modelo 036 registry tests. Find no Modelo 036
  golden outbound payload or generic-engine round trip, while the committed
  registry test verifies the active revision and the exact v43 corpus bytes.
- Run `uv run --no-sync pytest -q --tb=short
  src/cadrumo/domain/calculations/registry/tests/test_censo_modelo_registry_data.py::test_committed_modelo_036_registry_data_loads_as_active_censo_foundation
  src/cadrumo/domain/calculations/registry/tests/test_censo_modelo_registry_data.py::test_committed_modelo_036_record_design_source_matches_manifest`.

## Outcome

### `modelo-036-outbound-machine-file-2025-02-03-open` | `mandate-gated`

- **Candidate:** Modelo 036 outbound machine-file generation for the active
  `2025-02-03-y-siguientes` revision, covering the `alta`, `modificacion`, and
  `baja` event periods from `2025-02-03` with no registered end date.
- **Mandate:** `unproven`. The unchecked legacy row in
  `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md` asks to
  route Modelo 036 export/filing linkage, and the current registry declares a
  generic filing application link. Neither is an accepted decision or explicit
  current product goal requiring local Modelo 036 machine-file generation.
- **Exact authority window:** `aeat-dr-036-2025` registers definitive
  `DR036v43.xlsx` against revision `2025-02-03-y-siguientes`, event periods
  `alta`/`modificacion`/`baja`, inclusive start `2025-02-03`, open end. The
  source covers this exact candidate window. `DR036v42.xlsx` is separately
  labelled provisional and supplies no authority to the active revision.
- **Canonical implementation state:** `gap` for the candidate behavior: Modelo
  036 declares no export layout, so the existing generic `export_draft` and
  `parse_export_payload` path cannot render or round-trip a Modelo 036 machine
  file. The generic engine itself is delivered and fail-closed; no new renderer
  or parser is missing or permitted.
- **Real evidence or specimen:** official record-design authority
  `aeat-dr-036-2025` is `available` for layout interpretation and is registered
  as `record_design_layout` parity with `runner_required = false`. A real golden
  Modelo 036 outbound payload and mutation-sensitive generic round trip are
  `missing`; the record-design workbook is not a golden emitted file.
- **Retirement:** `false`. Modelo 036 is the active census foundation from
  `2025-02-03`; the retirement applies to Modelo 037, not this candidate.
- **Evidence block:** `true`. The required real golden Modelo 036 outbound
  payload is unavailable, so an eventual export claim could not yet satisfy the
  real-behavior evidence contract.
- **Four-condition gate:** `mandate_met = false`;
  `exact_authority_met = true`; `canonical_gap_met = false` because no current
  mandate makes the absent optional layout a required capability;
  `eligible_met = false` because real golden export evidence is unavailable.
- **Gate result:** `fail`.
- **Disposition:** `mandate-gated`.
- **Next action:** obtain an accepted product decision explicitly requiring
  local Modelo 036 machine-file generation for the `2025-02-03`-and-following
  window; until then, create no export layout, renderer, parser, test, or
  successor implementation step.

Focused verification passed: `2 passed in 16.00s`. No Reference correction was
required.

## Notes

- Intent-first Vaultspec RAG completed successfully in 5.9 seconds; no semantic
  fallback incident occurred.
- No production source, test, registry data, shared Reference, rolling audit,
  parent-plan checkbox, or index was changed. No staging or commit was
  performed.
