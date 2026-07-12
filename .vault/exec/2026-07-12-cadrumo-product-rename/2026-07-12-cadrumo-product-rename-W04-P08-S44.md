---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S44'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S44 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Rename MCP resource URI schemes and ## Scope

- `src/cadrumo/entrypoints/mcp/_resources.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
