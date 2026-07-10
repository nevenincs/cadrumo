---
tags:
  - '#exec'
  - '#mcp-protocol-hardening'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S15'
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
     The S15 and 2026-07-08-mcp-protocol-hardening-plan placeholders are machine-filled by
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
     The Emit resource_link content items in place of inlined bulk arrays on the identified verbs while keeping structuredContent the typed summary and ## Scope

- `src/aeat/entrypoints/mcp/_server.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Emit resource_link content items in place of inlined bulk arrays on the identified verbs while keeping structuredContent the typed summary

## Scope

- `src/aeat/entrypoints/mcp/_server.py`

## Description

- Call `thin_envelope(command_key, envelope)` on both result-build sites in `_server.py`: the direct-call path and the meta-`execute` path, so the two surfaces emit one identical shape.
- For each thinned array present as a non-empty list with a resolvable id, pop it from `envelope["result"]`, leave a `{key}_resource` URI and a `{key}_count` marker in the summary, and set `structuredContent` to the thinned envelope.
- Emit one SDK `ResourceLink` (`type="resource_link"`) content item per moved array via the `_resource_links` adapter; keep the full untouched envelope as the text `content` for a resources-incapable client.

## Outcome

- A `modelo.work.calculate` / `modelo.work.observations` result no longer inlines the observation provenance array in `structuredContent`; it carries `observations_resource` + `observations_count` and a `resource_link` the client fetches on demand. `ledger.evidence.list` thins its `rows` the same way.
- An error envelope, a zero-row result, or a result whose id is missing is left inline (nothing to thin), so no link is ever emitted that cannot resolve.

## Notes

- Thinning never mutates the source envelope (the text content still shows the complete result); `thin_envelope` returns copies. Proven by `test_thin_envelope_does_not_mutate_the_source_envelope`.
