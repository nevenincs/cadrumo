---
tags:
  - '#exec'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-plan]]"
---

# Record Modelo 037 outbound support as retired and prohibit new registry or export work

## Scope

- `src/cadrumo/_data/registry/aeat/`
- `.vault/reference/`

## Description

Adjudicated only the current outbound surface for Modelo 037. This is separate
from the already-closed declaration-extraction finding: the candidate here is
active machine-file generation or other outbound filing support, not inbound
parsing or historical catalogue preservation.

The exact authority is the reviewed BOE suppression recorded by
`orden-hac-1526-2024:art-1`, `orden-hac-1526-2024:df-unica`, and
`boe-modelo-037-historical-suppression` in
`src/cadrumo/_data/registry/aeat/legal/censo.toml`. It suppresses the active
Modelo 037 surfaces from 2025-02-03 and leaves Modelo 036 as the successor. The
active Modelo registry has no `037` definition, while the official corpus
inventory at
`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_037/manifest.json`
contains zero artefacts and records that no current or previous official index
exposed a matching record-design link.

The canonical implementation already enforces that decision. In
`src/cadrumo/domain/calculations/registry/_censo_modelos.py`, Modelo 037 is
historical metadata, may not acquire an active registry definition, cannot
create an active work-unit foundation, and is marked as superseded by Modelo
036. `ValidatedRegistryAuthority.modelo` in
`src/cadrumo/domain/calculations/registry/_authority.py` rejects a model absent
from the calculation registry. The shared export flow in
`src/cadrumo/domain/calculations/registry/_export.py` and
`src/cadrumo/application/filing/_export.py` also refuses export when no
registry-backed layouts or export identifiers exist. There is therefore no
Modelo 037 layout for the generic exporter to render and no missing
Modelo-specific implementation to add.

## Outcome

### `modelo-037-outbound-2025-02-03-open` | `retired`

- **Candidate:** Active Modelo 037 outbound machine-file generation or filing
  export for the authority window beginning 2025-02-03. Historical
  pre-suppression formats are outside this active candidate.
- **Mandate:** `absent`. The accepted authority mandates suppression and
  historical treatment, with Modelo 036 as successor; it does not mandate a
  current Modelo 037 export surface.
- **Exact authority window:** `2025-02-03` to open end, grounded in
  BOE-A-2025-410 / Orden HAC/1526/2024 article 1 and final provision, as
  captured by the reviewed legal and suppression-source entries in
  `legal/censo.toml`. This is exact retirement authority, not authority for an
  active exporter.
- **Canonical implementation state:** `delivered` for the required retirement
  and refusal behaviour. Modelo 037 is historical metadata only, has no active
  registry definition or snapshot/layout, cannot found active work units, and
  is superseded by Modelo 036. The existing generic registry/export path fails
  closed; no parallel Modelo 037 path is warranted.
- **Real evidence or specimen:** `not-required` for a retired active surface.
  The reviewed suppression authority is present. The Modelo 037 record-design
  manifest is an explicit zero-artefact negative inventory, not an export
  specimen and not a basis for reviving support.
- **Retirement:** `true`.
- **Evidence block:** `false`. Retirement resolves the candidate independently;
  the absence of a design artefact is corroborating negative inventory rather
  than the reason for deferral.
- **Condition booleans:** `mandate_met=false`;
  `exact_authority_met=true`; `canonical_gap_met=false`;
  `eligible_met=false`.
- **Gate result:** `fail`.
- **Disposition:** `retired`.
- **Next action:** `none`. Preserve Modelo 036 as the active successor. Do not
  add a Modelo 037 registry definition, export layout, renderer, parser, shim,
  active entry point, implementation test, or successor implementation step.

## Notes

- Grounding was bounded to the accepted ADR/research/reference/audit contract,
  the exact suppression entries, the Modelo 037 negative inventory, the censo
  ownership implementation, the generic registry/export refusal paths, and
  four existing real-behaviour test anchors. No broad RAG query was used.
- The focused verification command targeted:
  `test_modelo_037_is_historical_catalogue_metadata_not_active_registry_model`,
  `test_no_committed_modelo_037_toml_can_revive_active_support`,
  `test_modelo_036_is_active_event_triggered_foundation`, and
  `test_modelo_037_is_historical_metadata_superseded_by_036`. The command
  exceeded the 30-second execution limit before emitting a pytest result, so
  this record makes no test-pass or test-failure claim.
- No production code, tests, registry data, shared audit/reference document,
  plan, staging area, or commit was changed by this step.
