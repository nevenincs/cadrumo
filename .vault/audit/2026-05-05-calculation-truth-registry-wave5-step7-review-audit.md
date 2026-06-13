---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-wave5-step7-exec]]'
---

# `calculation-truth-registry` audit: `wave5-step7`

## Scope

Focused review of the Modelo 131 DPA/DID schema foundation, including export
field binding support and official record-design workbook extraction.

## Findings

- No blocking finding in the focused schema foundation slice.
- The export schema can now represent fields sourced from structured bindings,
  which prevents DPA and DID data from being flattened into synthetic casillas.
- The record-design inspector reads the official AEAT workbook rows directly
  and is read-only. It does not create TOML, mutate corpus files, or promote
  workbook rows into authority by itself.
- The current Modelo 131 registry covers the non-reserved 2026 DPA
  activity-detail fields and DID IBAN field as layout-authority-backed
  bindings, and the test compares those bindings to the official workbook
  coordinates rather than repeating the schema in test fixtures.
- The filing draft model now separates registry binding values from casilla
  values and supports repeated row-indexed binding values. This removes the
  assumption that every modelo value must be a flat casilla while preserving
  content-addressed draft identity.
- The generic export renderer now has a binding-row repeat path. Official DPA
  tables can be rendered by registry export layouts without a model-specific
  exporter once the layout is fully defined.
- Export parse-back also supports binding-row repeated records, preserving a
  roundtrip verification route for table-shaped official layouts.
- Tests prove the actual official Modelo 131 workbook shape: 2019-2023 has
  only page sheets, while 2024, 2025, and 2026 expose DPA and DID sheets.
- Registry verification still reports no Modelo 131 export layout. That is the
  correct state until serialization, parse-back, direct-debit guards, and
  roundtrip verification are implemented.

## Recommendations

- Continue by implementing the 2026 DPA/DID registry export layout from the
  official workbook rows, then compare the 2024 and 2025 field signatures
  before deciding whether they can reuse or need year-scoped export layouts.
- Do not expose Modelo 131 filing-grade export until DPA, DID, liquidacion
  fields, roundtrip tests, and direct-debit remote-state guards are complete.
