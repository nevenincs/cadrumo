---
tags:
  - '#audit'
  - '#developer-leak-cycle1-registry-tomls'
date: '2026-05-18'
modified: '2026-05-18'
related: []
---

# `developer-leak-cycle1-registry-tomls` audit: cycle 1 phase 1 registry TOML developer-leak sweep

## Scope

Audit of every TOML under `src/aeat/_data/registry/aeat/modelos/` (32 files: 26 single-file modelos plus the Modelo 100 manifest and six revisions) for identifier, label, or citation strings that encode software-development concepts where AEAT operator-facing concepts are required. Driven by the confirmed leak `header_key = "developer_nif"` in `130.toml`, which collapses the AEAT "NIF del presentador" (declarant operator) onto the unrelated "software developer NIF" concept.

## Findings

All findings classified `leaked-dev-metadata` (i.e. wrong concept embedded in a publicly-canonical field). Each occupies offset 101, length 9 inside the BOE/AEAT fichero header for that modelo, which BOE/AEAT documentation labels "NIF del presentador / declarante". None of these positions describe the software developer; AEAT's separate "NIF del programa" / "Diseño de registro - software" fields (when present) live elsewhere in the header. Every leak in this surface should be renamed to the operator concept (`presenter_nif` / `presentador_nif`, with matching `id` of the form `modelo-XXX-envelope-presenter-nif`).

### `src/aeat/_data/registry/aeat/modelos/111.toml:616-620` — `id = "modelo-111-envelope-developer-nif"` / `header_key = "developer_nif"` — leaked-dev-metadata — rename to `modelo-111-envelope-presenter-nif` / `presenter_nif`.

### `src/aeat/_data/registry/aeat/modelos/115.toml:286-290` — `id = "modelo-115-envelope-developer-tax-id"` / `header_key = "developer_tax_id"` — leaked-dev-metadata — rename to `modelo-115-envelope-presenter-nif` / `presenter_nif`.

### `src/aeat/_data/registry/aeat/modelos/123.toml:418-422` — `id = "modelo-123-envelope-developer-tax-id"` / `header_key = "developer_tax_id"` — leaked-dev-metadata — rename to `modelo-123-envelope-presenter-nif` / `presenter_nif`.

### `src/aeat/_data/registry/aeat/modelos/123.toml:1473-1477` — `id = "modelo-123-2019-envelope-developer-tax-id"` / `header_key = "developer_tax_id"` — leaked-dev-metadata — rename to `modelo-123-2019-envelope-presenter-nif` / `presenter_nif`.

### `src/aeat/_data/registry/aeat/modelos/130.toml:697-701` — `id = "modelo-130-envelope-developer-nif"` / `header_key = "developer_nif"` — leaked-dev-metadata — rename to `modelo-130-envelope-presenter-nif` / `presenter_nif`. (Originating exemplar in the user's brief.)

### `src/aeat/_data/registry/aeat/modelos/202.toml:1253-1257` — `id = "modelo-202-envelope-developer-nif"` / `header_key = "developer_nif"` — leaked-dev-metadata — rename to `modelo-202-envelope-presenter-nif` / `presenter_nif`.

### `src/aeat/_data/registry/aeat/modelos/202.toml:4984-4988` — `id = "modelo-202-2023-2024-envelope-header-header-developer-nif-po"` / `header_key = "developer_nif"` — leaked-dev-metadata — rename to `modelo-202-2023-2024-envelope-presenter-nif` / `presenter_nif` (also drop the duplicated `header-header-` and trailing `-po` artefacts; both look like generator slugs rather than AEAT terms).

### `src/aeat/_data/registry/aeat/modelos/202.toml:6498-6502` — `id = "modelo-202-2019-2022-envelope-header-header-developer-nif-po"` / `header_key = "developer_nif"` — leaked-dev-metadata — rename to `modelo-202-2019-2022-envelope-presenter-nif` / `presenter_nif` (same `header-header-...-po` slug concern).

### `src/aeat/_data/registry/aeat/modelos/232.toml:256-260` — `id = "modelo-232-2018-envelope-developer-nif"` / `header_key = "developer_nif"` — leaked-dev-metadata — rename to `modelo-232-2018-envelope-presenter-nif` / `presenter_nif`.

### `src/aeat/_data/registry/aeat/modelos/232.toml:3131-3135` — `id = "modelo-232-2016-envelope-developer-nif"` / `header_key = "developer_nif"` — leaked-dev-metadata — rename to `modelo-232-2016-envelope-presenter-nif` / `presenter_nif`.

### Non-findings (verified clean)

- All other matches for `developer|dev_|wip|todo|tmp|temp|staging|claude|codex|haiku|sonnet|gpt|agent|phase|wave|step|W##|P##|S##` resolved to legitimate AEAT/BOE Spanish text ("todo el año", "Programa de preparación", "programas de apoyo a acontecimientos"), legitimate BOE design-record `page_NN` selectors, legitimate AEAT type codes (`P102`), or sectional comment headings — not leaked dev metadata.
- `label`, `notes`, `description`, `quote`, `reference`, `locator` fields contained no TODO/FIXME/agent-name/ADR-ref/plan-ref/audit-ref strings under this scope.

## Recommendations

Pair each rename with: (a) propagation through any registry callers that bind the header by literal `header_key` or `id`; (b) a roundtrip-test sweep across the affected fichero envelopes asserting strict equality after rename (so a save-as-`developer_nif`, load-as-`presenter_nif` regression is forced to surface); (c) a source-citation check that the corresponding `aeat-dr-XXX-YYYY-vNN` documents actually label this position "NIF del presentador" so the registry's own provenance line is preserved through the rename.

## Counts

- real-aeat-field: 0
- leaked-dev-metadata: 10
- ambiguous-needs-adjudication: 0
