---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:b6931b4fd36ef35cc8f6f0343f2f02bd7f77e4fc50e6f7f1d63af35ce061bce9'
step_id: 'S313'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Rewrite the outbound LLM adapter facade docstring to describe what that package now is, four persistence-backed stores, and point the client surface at the sibling package that owns it, rather than describing the pre-split surface or promoting symbols back

## Scope

- `src/cadrumo/adapters/outbound/llm`

## Description

- Read the outbound adapter package's facade docstring at HEAD before planning
  any rewrite.
- Sweep the sibling `llm` package for docstrings still describing the
  pre-split outbound surface, which is the direction the row did not name.
- Correct the two that were found, in the S317 commit.

## Outcome

PREMISE EXPIRED on the row's own target, DELIVERED on the residual it did not
reach.

The facade docstring the row asks for already exists at HEAD and already says
what the row wants said: it opens by naming the package as the
persistence-backed stores beside an outbound model call, states that its
`__all__` is four encrypted stores plus the two telemetry records and nothing
else, and points the completion surface at the sibling `llm` package by name,
listing the client, the request and response records, the provider enum, the
prompt registry, the strict model types, the rasterisation helper and the
error hierarchy as living there rather than here. It promotes nothing back.
There was no rewrite to perform.

The staleness was real but pointed the other way, which is what makes this a
delivery rather than a bare retraction. Two docstrings INSIDE `llm` still
described the pre-split arrangement: `llm/_models.py` opened by asserting that
the outbound facade re-exports the request, response and provider records,
which that facade's own `__all__` contradicts, and the Anthropic adapter's
class docstring said its provider class attribute identifies it to an
`adapters.outbound.llm` factory, while the adapter is in fact built by the
client's own `_build_adapter` behind the optional-SDK import boundary and that
package constructs no adapter at all. Both are corrected.

## Notes

Neither residual would have been caught by the gate landed under S317, and
that is worth recording rather than glossing: both are `:mod:` roles naming a
package that genuinely exists, so the role RESOLVES and the falsehood lives in
the surrounding prose claim about what that package re-exports. A structural
check reaches the citation, not the sentence. These two were found by reading,
which is the same limit the sibling well-formedness gate states about itself.
