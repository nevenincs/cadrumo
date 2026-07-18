---
tags:
  - '#exec'
  - '#distribution-harness-identity'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S04'
related:
  - "[[2026-07-18-distribution-harness-identity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace distribution-harness-identity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-07-18-distribution-harness-identity-plan placeholders are machine-filled by
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
     The Prefix the orientation-prompt embedded rule-resource URI (the synthetic cadrumo://rule/operating-rules leaf) so every embedded reference carries the cadrumo- prefix, and update the prompt and resource projection tests and ## Scope

- `src/cadrumo/entrypoints/mcp/_prompts.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prefix the orientation-prompt embedded rule-resource URI (the synthetic cadrumo://rule/operating-rules leaf) so every embedded reference carries the cadrumo- prefix, and update the prompt and resource projection tests

## Scope

- `src/cadrumo/entrypoints/mcp/_prompts.py`

## Description

- Prefixed the orientation-prompt embedded rule-resource URI in `_prompts.py`: the synthetic `resource_uri(HarnessResourceKind.RULE, "operating-rules")` leaf is now `"cadrumo-operating-rules"`, so the embedded reference in `cadrumo://rule/...` carries the `cadrumo-` product prefix.
- Updated the prompt-projection assertion in `test_prompts.py` to expect `cadrumo://rule/cadrumo-operating-rules`.

## Outcome

- This is the one non-derived MCP projection identifier (a synthetic aggregate label for the concatenated operator-rules bundle, not a single rule file), so no other surface changes. The per-skill embedded SKILL URIs and the RULE/PERSONA resource stems all auto-derive from the renamed filenames and were already compliant after P01.
- Green gates: `test_prompts.py` + `test_harness_delivery.py` 32 passed; ruff check + format + ty clean on the two touched files.
- The distribution-identity verifier self-test (`test_verify_distribution_identity.py`, which still pins the pre-migration `["operating-rules"]` failure) stays red by design and is re-baselined in P04.S10; it was not touched.

## Notes

- No incidents.
