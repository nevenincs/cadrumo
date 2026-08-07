---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:bfdd2e3521adf1d62849f0f257752659f0f1749b41ae3dff297c8801c8fb1476'
step_id: 'S71'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Append a consent-ledger entry at the dispatch choke point in the same path that honours a token, refusing transmission when the append fails, gated by mutation: break the append and the dispatch must refuse

## Scope

- `src/cadrumo/llm/_client.py`

## Description

The off-host consent gate refused an unconsented dispatch but recorded nothing
about the ones it permitted. This adds the audit ledger, placed so completeness
is a property of the code path rather than of a caller remembering.

## Outcome

The append lives inside `_require_evidence_consent`, in the branch that HONOURS
the token -- the same function that raises when the token is absent or the
deployment bars the read. That branch is reached before the response cache is
read and before any provider adapter is constructed, so there is no ordering in
which a consented request reaches the wire without its entry already written. A
failed append raises rather than degrading: a best-effort log that can silently
miss an entry is worse than none, because a later audit reads it as complete.

The entry records that a transmission was consented, never what was
transmitted: the SHA-256 content address, the resolved provider and model, the
operator surface that took the acknowledgement, the bucket the dispatch ran
under, and the timestamp. There is no field for prompt or response text.

The store is a fourth sibling to the three LLM diagnostic stores and follows
their injection shape, but differs on two axes deliberately. It is not swept by
the retention pass -- a consent withdrawal enumerates it to find which artefacts
depend on a cloud read, so an aged-out entry would make that withdrawal silently
incomplete -- and its write refuses rather than swallowing.

Modified files:

- `src/cadrumo/adapters/outbound/llm/_consent_ledger.py` (new): the entry model
  and the append/read store.
- `src/cadrumo/adapters/outbound/llm/__init__.py`: facade export.
- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py` and its
  package facade: a new profile-local, structured-custody secure-object
  namespace. It carries no path definition, so it inherits the `secure_object`
  durability declaration and needs no new persisted-format entry.
- `src/cadrumo/llm/_client.py`: the injected collaborator and the append at the
  choke point; the resolved model is threaded into the guard so the entry can
  record it.
- `src/cadrumo/adapters/outbound/llm/tests/test_evidence_consent_ledger.py`
  (new): five behavioural tests against a real encrypted backend.

## Verification

`pytest -n0 -p no:cacheprovider -m unit` (the default lane; `integration` is
deselected), five tests, all passing.

Positive control first, because the refusal claim is worthless without it: with
the append working, a consented off-host evidence request DOES reach the
provider adapter and exactly one entry lands with the right address, provider,
model and surface. A second test asserts the persisted bytes contain neither a
distinctive prompt token nor a distinctive response token.

Two mutations, both applied from outside the repository as pytest plugins, each
printing an observable delta before the run so a green result could not be
mistaken for a landed mutation.

Mutation one replaces only the ledger's `append` with a silent no-op: three of
five tests red. Two reds are the property itself (zero entries where one was
required). The third, the no-bucket-session refusal test, red because the
dispatch proceeded past the ledger and a downstream storage guard refused
instead -- a genuine flip, but a confounded one, since everything after the
append also needs storage. That confound is why the fifth test exists: it keeps
storage healthy, primes the cache with a successful consented call, proves the
second call really is served from cache, and only then swaps in a failing
ledger. That test is unaffected by mutation one (it injects its own ledger),
which is the correct outcome rather than a gap.

Mutation two is the narrower one: it replaces `_require_evidence_consent` with a
byte-identical copy minus the single append call, leaving both refusal branches
intact. Four of five tests red, and the ordering probe reds with `DID NOT RAISE
LLMConsentError` -- the cache hit was served unrecorded, which is exactly the
silent gap this Step closes.

## Notes

The append is ordered ahead of the cache read, so a consented invocation served
from a primed entry is recorded too. That over-records rather than under-records
and is the honest direction: the response is still cloud-derived, so a
withdrawal must list it as a re-derivation candidate.
