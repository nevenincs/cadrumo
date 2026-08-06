---
tags:
  - '#exec'
  - '#mcp-protocol-hardening'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:1b1a449db35fd74fad19d05903576581063548cb5a73004f590df3f910e200b4'
step_id: 'S15'
related:
  - "[[2026-07-08-mcp-protocol-hardening-plan]]"
---

# Emit resource_link content items in place of inlined bulk arrays on the identified verbs while keeping structuredContent the typed summary

## Scope

- `src/aeat/entrypoints/mcp/_server.py`

## Description

- Call `thin_envelope(command_key, envelope)` on both result-build sites in `_server.py`: the direct-call path and the meta-`execute` path, so the two surfaces emit one identical shape.
- For each thinned array present as a non-empty list with a resolvable id, pop it from `envelope["result"]`, leave a `{key}_resource` URI and a `{key}_count` marker in the summary, and set `structuredContent` to the thinned envelope.
- Emit one SDK `ResourceLink` (`type="resource_link"`) content item per moved array via the `_resource_links` adapter; keep the full untouched envelope as the text `content` for a resources-incapable client.

## Outcome

- A `modelo.work.calculate` / `modelo.work.observations` / `modelo.work.revision` result no longer inlines the observation provenance array in `structuredContent`; it carries `observations_resource` + `observations_count` and a `resource_link` the client fetches on demand. `ledger.evidence.list` thins its `rows` the same way. (`modelo.work.revisions` nests per-entry revisions rather than a single flat array addressable by one id, so it is left inline — a clean follow-up if per-entry thinning is wanted.)
- An error envelope, a zero-row result, or a result whose id is missing is left inline (nothing to thin), so no link is ever emitted that cannot resolve.

## Notes

- Thinning never mutates the source envelope (the text content still shows the complete result); `thin_envelope` returns copies. Proven by `test_thin_envelope_does_not_mutate_the_source_envelope`.
