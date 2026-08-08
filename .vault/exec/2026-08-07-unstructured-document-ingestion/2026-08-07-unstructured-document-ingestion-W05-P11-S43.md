---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:1a52b44fec81390d804278611b6bb6ab5661961357c1a8638d1050687aade9ca'
step_id: 'S43'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# `unstructured-document-ingestion` exec: `W05-P11-S43`

## What the assertion said, and why it had to change

`test_every_provenance_stamp_a_reader_can_mint_names_a_local_transport` asserted
that every stamp a reader could mint named an on-host transport. It was true
when it shipped: the cloud transport had just been deleted and the provider axis
really had collapsed. It is not true at HEAD. Off-host evidence reading was
re-sanctioned behind the consent gate and three readers took a provider back, so
the gate described a property the tree no longer has -- while reading green,
because it built two classifiers by name and those two are still on-host.

That is the more important half of the finding. The gate's own docstring claimed
it ran "over the readers that actually exist rather than over a hand-kept list,
so a reader added later is covered by construction". It named two of five. Three
further stamp producers shipped in the same package, one of which could already
mint an off-host stamp from configuration alone.

## The narrowing

Narrowed by the property that still holds rather than by dropping the readers
that stopped satisfying it -- those move to a second assertion, not out of the
module.

`_READERS_WITH_NO_PROVIDER_AXIS` (`LocalTextLLMClassifier`,
`LocalVisionLLMClassifier`) are reachable with no consent token. They must stamp
on-host, and the structural claim underneath -- that their `__init__` declares no
`provider` parameter -- is asserted rather than trusted, so the on-host result is
a property of the class instead of an observation about the one instance built.

`_READERS_WITH_A_PROVIDER_AXIS` (`TextInvoiceFieldExtractor`,
`LocalVisionDocumentTranscriber`, `SemanticColumnRoleMapper`) are held to
honesty in both directions: constructed on-host they stamp `local`, constructed
with a named off-host provider they stamp exactly that transport and never
`local`. The on-host direction is the positive control; without it, a reader that
had stopped stamping anything meaningful would satisfy "not local" by accident.

A third assertion checks the partition is total against the stamp producers
discovered by walking `src/cadrumo/llm/*.py` for classes declaring `decided_by`
or `transcriber_identity`. Discovered from source rather than by importing the
package, because a reader class that failed to import would silently shrink the
discovered set to something the declaration still covers.

Transport is now read through `provenance_stamp_transport` rather than by
slicing on `:`. The slice this replaces re-implemented the stamp grammar inside
the gate that checks it, and a producer and a checker each carrying their own
copy of a grammar agree until the grammar changes.

## Proof

Six mutations from a pytest plugin outside the repository; no tracked file was
touched. Baseline 7 collected, 7 passed.

Each mutation reddened exactly the assertion it targets. An unconsented reader
stamping `openai` and a class growing a `provider` parameter each reddened the
on-host test. An off-host read stamping `local` -- the live defect the honesty
half exists for -- reddened the honesty test on its own message, not on the
control. Breaking the positive control reddened the same test on the control
line instead, which is what proves the control does its own work rather than
riding the honesty check. Planting an undeclared stamp producer in a scratch
tree reddened the totality test. Dropping a declared reader reddened two.

Two constructions are pinned deliberately. The column-role mapper's model is
named rather than resolved, because resolution runs the on-host hardware
admission check and would make the gate's result a property of the machine --
it refused outright on this box for 1.8 GiB free against a 2.3 GiB floor. And
the text extractor's authority values are injected rather than resolved, because
resolving real rates couples a transport assertion to registry load, which
failed twice during this work with `registry directory changed during cache
fingerprinting` from concurrent peer writes.

## Verification

    uv run --no-sync pytest src/cadrumo/tests/test_cloud_transport_fully_deleted.py \
      src/cadrumo/llm/tests/test_local_text_reader_wiring.py \
      src/cadrumo/llm/tests/test_provenance_stamp_singularity.py -n0 -q -m unit
    16 passed

    uv run --no-sync ruff check / ruff format --check / ty check
    clean on all four changed source files

## Prose the amendment made false

Three docstrings still instructed authors to treat the transport axis as
single-valued, and one of them said so as a rule for code: "do not treat the
axis as multi-valued when deciding what a fresh classification can be". A
consent withdrawal enumerates cloud-derived artefacts by exactly that segment,
so code written to that instruction would survey for a value it had been told
could not occur. All three corrected in the same commit; the deleted-symbol
comment naming the operator surfaces was also stale, since a CLI surface does
now mint a token -- under different flag names.
