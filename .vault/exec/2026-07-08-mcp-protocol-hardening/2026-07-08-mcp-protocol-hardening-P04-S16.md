---
tags:
  - '#exec'
  - '#mcp-protocol-hardening'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S16'
related:
  - "[[2026-07-08-mcp-protocol-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace mcp-protocol-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S16 and 2026-07-08-mcp-protocol-hardening-plan placeholders are machine-filled by
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
     The Update the affected per-verb output schemas in lock-step with the thinned payload shapes and ## Scope

- `src/aeat/entrypoints/mcp/_tools.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update the affected per-verb output schemas in lock-step with the thinned payload shapes

## Scope

- `src/aeat/entrypoints/mcp/_tools.py`

## Description

- Route `_output_schema_for` in `_tools.py` through `thin_output_schema(command_key, schema)` so a thinned verb's declared output schema drops the moved bulk-array property and declares the two summary markers (`{key}_resource` string, `{key}_count` integer) in lock-step with `thin_envelope`.
- Strip the moved property from the schema's `required` list and prune any `$defs` entry orphaned by the removed property (iterated to a fixpoint over `$ref` reachability, so a shared definition is always kept).

## Outcome

- The advertised output schema now matches the emitted thinned `structuredContent`, and the reduction is real (not just a marker swap): `modelo.work.calculate` 8843→7169, `modelo.work.observations` 3133→1338, `ledger.evidence.list` 2219→533 chars, with the orphaned `ObservationPayload` `$def` pruned.
- The static size-budget gate (`test_result_size_budget.py`, P04.S17) measures the thinned shape and stays green; `test_thin_output_schema_strictly_shrinks_the_schema` is the anti-tautology proof that thinning reduces every thinned verb's schema.

## Notes

- The output schema describes the result model while `structuredContent` is the full envelope (a pre-existing shape the campaign did not introduce); thinning keeps the result and its schema in lock-step, which is the S16 contract, and does not touch that pre-existing envelope-vs-result framing.
