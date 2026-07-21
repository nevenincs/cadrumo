---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
step_id: 'S44'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename MCP resource URI schemes

## Scope

- `src/cadrumo/entrypoints/mcp/_resources.py`

## Description

- Replace the product-owned MCP resource URI scheme with `cadrumo://` across construction, templates, parsing, reads, and errors.
- Rename product resource-template identities to `cadrumo-<kind>` without changing AEAT legal and registry authority content.
- Retarget direct resource, bulk-resolution, harness-delivery, and result-thinning tests to the canonical hard-cut scheme.
- Reject former `aeat://` resource addresses with no alias or fallback.

## Outcome

The MCP resource boundary now exposes only `cadrumo://<kind>/<name>` and
`cadrumo://<kind>/{name}` addresses. Concrete enumeration, template listing,
parsing, bundled reads, bucket-scoped refusal, server adaptation, and thinned
resource links all use the same `resource_uri` constructor. AEAT remains in
authority-facing descriptions, legal corpus examples, and registry taxonomy.

## Notes

- Focused resource-owned tests passed: 47 tests in 25.64 seconds.
- Ruff, formatting, former-scheme residue, and scoped diff checks passed.
- Two prompt URI assertions discovered during S44 were transferred to Cgeap's S45 ownership because `_prompts.py` is explicitly outside this Step; neither `test_prompts.py` nor prompt production code is staged here.
- Corpus-search tool URI assertions remain on their current producer until that separately owned producer is renamed; S44 does not claim or stage them.
