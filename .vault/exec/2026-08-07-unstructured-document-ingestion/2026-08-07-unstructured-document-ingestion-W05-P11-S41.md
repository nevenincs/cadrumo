---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:9c6ed19a1f4f3cb7b288b27eb2eaa34820ebae7bc455cf72508f9572e130cde7'
step_id: 'S41'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Context

Reconstructed by the coordinator from the implementing lane's report, verified
against HEAD, rather than authored by the implementer. The lane delivered this
Step's substance while executing `W02.P05.S17`, surfaced that fact rather than
letting the row read as unstarted, and correctly declined to check a row that was
not its own.

## What is enforced, and where

`LLMClient._require_evidence_consent` refuses an off-host dispatch of taxpayer
evidence that carries no per-invocation consent token. It sits at the client's
single dispatch point, and the module's own reasoning for that placement is the
one worth preserving: which requests may leave the host is a property of the
dispatch, never of each caller remembering to pin a provider. A caller may pin
the local provider as documentation, but no pin is load-bearing.

Two orderings carry the guarantee, both deliberate and both verified at HEAD.
The check runs **before the cache read**, so an entry primed under consent cannot
make a later unconsented invocation succeed — a cache hit does not look like a
transmission decision, so a sticky grant arriving through that channel would be
invisible to audit. It also runs **before adapter construction**, which turned
out to matter concretely: the implementing lane's first positive-control run
failed on a missing provider credential, which is the "absent credential that
looks like a control" shape. Every case in the suite now supplies a working
credential against a loopback endpoint, refusals included, so no refusal can be
the credential rather than the gate.

Default-off lives at the readers rather than on the request. The request model
defaults `evidence_derived` to false, because a restrictive default there would
have gated unrelated work on day one — loud and immediate. The readers default
`public_corpus` to false, so a caller who says nothing gets the gate and naming
the corpus is the deliberate act. The restrictive default sits where the failure
would be silent.

The consent token is excluded from serialisation, so it enters neither the cache
key nor any persisted record, and absence is expressed by omitting the key rather
than by an explicit null — a test asserting the field is absent cannot pass
against the payload that would fail in production.

## The dispatch surface is bounded

Measured at HEAD rather than assumed: the provider call appears exactly once in
non-test source, and no adapter class is exported on the package facade, so
reaching one requires a private-submodule import the import-hygiene gate already
forbids across packages. That is the residual, and it is bounded rather than
open.

## Proof

Six mutations from a plugin outside the repository, no tracked file touched.
Removing the gate reddened four cases; dropping the gestor bar, dropping the
deployment opt-in, unmarking the reader, and reordering the dispatch each
reddened exactly one; deleting the call from source reddened two.

Two results are worth reading together. Removing the gate left the deletion
gate's wiring assertion green, which is correct rather than a miss: that
assertion reads source, so only the source-level deletion reds it, and it did.
The reordering mutation failed on the ordering comparison itself rather than on
the guard that all three calls are present, which proves the ordering assertion
does its own work instead of riding the presence check.

The caller's abstract syntax tree was walked rather than its source text sliced,
because the test's own docstring names the very symbols a substring scan would
match — the same trap that produced three unusable gates elsewhere in this
campaign. Every refusal case asserts on an empty request queue at the endpoint,
not only on the exception, so "refused" means nothing left the host rather than
an error was raised somewhere.

A later independent probe of the reach-around — widening the router wrapper's
signature and pointing it at a cloud provider — was refused by this gate with
zero bodies at the endpoint. That probe's own positive control initially could
not transmit either, which would have made the negative worthless; it was moved
into the suite where a real transmission is possible, and only then did the
refusal discriminate.

## What this Step does not deliver

Nothing mints a token at an operator-facing boundary, so in production this gate
refuses every off-host evidence read. That is the correct default-off posture
rather than a defect, and it is not the full lifecycle: the minting Step is what
makes the consented route reachable by a person rather than only by a test.

The confirm surface has no independent behavioural case. It is gated
transitively, because confirming re-runs the extraction through this same choke
point, and the implementing lane declined to write a structural "confirm calls
extract" assertion instead — such an assertion cannot see what a caller does with
what it raises, which is the failure class this campaign hit three times. The gap
is named rather than covered by a weak instrument.
