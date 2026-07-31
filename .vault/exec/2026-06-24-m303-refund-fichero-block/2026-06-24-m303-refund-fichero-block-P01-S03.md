---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:230eb6a83fad036e76fe4ed241b79d84d476d6f03b78918bded7d4d97b887e79'
step_id: 'S03'
related:
  - "[[2026-06-24-m303-refund-fichero-block-plan]]"
---

# Add export_headers redeme to the redeme_enrolled schema field for the page-1 indicator

## Scope

- `src/aeat/_data/registry/aeat/user_profile/schema.toml`

## Description

- Add the `redeme` export-header alias to the `redeme_enrolled` boolean field's `export_headers` list on the central schema so the fichero page-1 REDEME indicator can resolve from the standing profile fact.
- Keep the field `sensitivity = "financial"` and grounded in `rd-1624-1992:art-30`, with its model selector and schedule predicate wiring intact.

## Outcome

- The `redeme_enrolled` field carries `export_headers = ["redeme"]` in `src/aeat/_data/registry/aeat/user_profile/schema.toml` at HEAD.
- The M303 header composer resolves the `redeme` header to the REDEME byte at DR303 page-1 offset 110, verified by the golden-SHA fichero tests which assert the byte value at offset 110 for both a REDEME and a non-REDEME filer.

## Notes

- This record documents the verified landed state at HEAD.
