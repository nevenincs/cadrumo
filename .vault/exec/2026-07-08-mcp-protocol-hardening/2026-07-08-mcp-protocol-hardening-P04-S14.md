---
tags:
  - '#exec'
  - '#mcp-protocol-hardening'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:5c76c6b48acc4a87e6231776d0cfff826ad293c9ef58d5695987eb538597f6b3'
step_id: 'S14'
related:
  - "[[2026-07-08-mcp-protocol-hardening-plan]]"
---

# Add resource templates and read handlers for the bulk payload classes (calculation observations, evidence rows, corpus excerpts) resolved from persisted state

## Scope

- `src/aeat/entrypoints/mcp/_resources.py`

## Description

- Add `OBSERVATIONS` and `EVIDENCE` resource kinds plus their template descriptions to `_resources.py`; both are template-only (`aeat://observations/{name}`, `aeat://evidence/{name}`), never concretely enumerated.
- Declare the single thinning + resolution authority in the new `_result_thinning.py`: `THINNED_VERBS` (which verbs move which result array, to which kind, keyed by which id) and `BULK_RESOLUTION` (which read verb re-materialises each kind, and its result field).
- Add the resource read handler in `_server.py` (`_resolve_bulk_resource`): a bucket-scoped resource is resolved by re-running its owning read verb's descriptor through the existing supervised subprocess (`_run_subprocess_tool`) and returning that verb's bulk field as a JSON array; an active-bucket resolver cross-checks the URI id against the resolved `result`.
- Refuse in-process reads of bucket-scoped kinds in `read_harness_resource` (they carry no active bucket session); expose `parse_resource_uri` and `BUCKET_SCOPED_RESOURCE_KINDS` for the server to route on.

## Outcome

- `aeat://observations/{calculation_revision_id}` resolves via the `modelo.work.observations` verb; `aeat://evidence/{bucket_id}` via `ledger.evidence.list`. Corpus excerpts (the plan's third named class) already shipped as `aeat://corpus/{ref}` under the sibling discovery ADR and are reused unchanged.
- Table↔surface drift gates in `test_result_thinning.py` bind every declared verb, field, kind, and resolver to the live descriptor surface; `test_bulk_resource_resolution.py` proves the templates are advertised and in-process reads of bucket kinds are refused.

## Notes

- Architectural finding driving the design: the MCP server process holds NO active bucket session (every tool runs as a subprocess that unlocks its own key — confirmed empirically: an in-process catalogue load raises `StorageValidationError: no active bucket session`). Bucket-encrypted observations/evidence therefore CANNOT be read in-process; resolution re-runs the owning read verb as a subprocess so it carries the session. This is why the read handler is a subprocess resolver, not a pure function like the bundled skill/rule/persona/corpus resolvers.
- Evidence rows resolved are the record METADATA the `ledger.evidence.list` verb already emits (never attachment bytes), so `sensitive-financial-data-secure-storage-only` is preserved.
- The literal subprocess-session hop is exercised in a live session and by the existing call-runtime/dispatch tests; it is not re-mockable against the in-process ephemeral-key fixtures (a child process cannot see them), so no mock stands in for it.
