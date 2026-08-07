---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:3b2d52fe2fd71fcd0240785bae9fda0dfa01d21708ece4bf014aabaf9c88f13c'
step_id: 'S80'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Scope

Add per-model parameter support to the transport capability axis and omit
unsupported parameters at the dispatch point, gated by adapter tests proving the
parameter is absent from the wire shape.

## What landed

Committed as `f3b5fe88fa` — 4 files, 229 insertions, 26 deletions.

- `_providers/base.py` — `ProviderRequest.temperature` widened to `float | None`;
  `_ProviderAdapter.unsupported_parameters(model)` added.
- `_providers/anthropic.py` — `build_message_kwargs` extracted.
- `_client.py` — `_omit_unsupported_parameters`, beside `_require_image_support`.
- `tests/test_parameter_capability_boundary.py` — 6 cases.

## The measured ceiling this removes

`temperature` was sent unconditionally and populated upstream on every request,
so current top-tier models rejected it with a 400 and the product could reach
only the older generation. The ceiling was artificial: nothing needed the
parameter, it was simply always present.

## Two halves of one defect

The silently-dropped `images` field and the always-sent `temperature` are the
same shape — a request field the transport assumed was universal. One was
dropped without telling anyone; one was sent without asking. That
`supports_images` exists because of the first while nothing analogous existed
for the second is the defect made visible in the code.

## The asymmetry, keyed on the size of the harm

The two capability axes end in different verbs, and that is deliberate rather
than an inconsistency:

- **Images REFUSE.** The fallback for a dropped image is a model answering about
  a document it never received, and answering confidently. Unbounded harm.
- **Parameters OMIT.** The fallback for an omitted sampling parameter is the
  vendor's own default. Bounded, and usually invisible.

The defaults follow the same logic and are therefore opposite.
`supports_images` defaults restrictive, so a new adapter is text-only until it
has genuinely implemented the image path. `unsupported_parameters` defaults to
the empty set, because a restrictive default there would have stripped
`temperature` from every working provider on the day it landed. The restrictive
default belongs where the failure is silent, not where it is merely a different
temperature.

## Declared per MODEL, not per adapter

That is where vendors actually differ: the same Anthropic adapter serves models
that accept `temperature` and models that refuse it, so an adapter-wide flag
cannot express the constraint. The capability takes the model identity and
answers for that model.

## Absence is the omission of the key

Expressed by not adding the key, never by passing `None`. The SDK forwards an
explicit `None` as JSON `null`, which is a stated value and draws the same
rejection the number would. A test asserting `kwargs["temperature"] is None`
would pass against exactly the payload that fails in production, so the
assertions are on membership.

## Why the extraction was necessary before the test could exist

`temperature` was a keyword argument to `messages.create`, not an entry in a
payload dict, passed at two nearly identical call sites differing only in
whether `system` was present. A parameter's ABSENCE is not assertable while the
payload exists only as inlined keyword arguments, so `build_message_kwargs` was
extracted the way `build_user_content` had been — the wire shape is now
constructible with no API key, no network and no SDK.

The extraction also collapsed the duplicated call sites. That duplication is
why `temperature` appeared twice, and why a one-site fix would have left the
other path still sending it.

## Verification

```
test_parameter_capability_boundary.py     6 passed
full llm suite   272 tests ran; 1 DESELECTED   271 passed
```

**Mutation proven**, applied from outside the repo as a pytest plugin loaded
with `-p`, so no tracked file was edited. Reinstating "send `temperature`
unconditionally, defaulting when unset" reds **exactly 2 of 6**: the wire-shape
absence case and the dispatch-clearing case. The other **4 still pass** — the
two positive controls (a supplied temperature reaches the wire; a tolerant model
keeps it), the permissive-default case, and the system-prompt case.

A targeted 2-of-6 rather than a wipeout is the signal worth recording: it shows
the assertions discriminate on omission specifically, where a total red would
show only that something broke.

## Unrelated failure observed, not caused

`test_injection_regression.py::TestWhatTheAnchorCheckDoesNotCatch::test_a_short_figure_anchors_inside_a_longer_printed_one`
failed identically in the baseline before any edit here, has no reference to
this Step's symbols, and its own docstring says it asserts "current behaviour,
not endorsed" for a gap needing a boundary-aware anchor search. It reads as a
test pinning pre-fix behaviour that did not move when the gap was closed. Left
untouched; loosening its assertion would be the wrong direction.
