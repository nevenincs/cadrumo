---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:aea0406080a1e3fc6622b434b019498b742ecf4280ceaced8131baeb2f27f70a'
step_id: 'S91'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Context

Reconstructed by the coordinator from the implementing lane's reports, verified
against HEAD, rather than authored by the implementer. The lane ran out of
context after landing the gate and chose to hand over a precise statement rather
than write this badly; every figure below was re-measured before it was written.

## What changed

The unstructured readers now declare `supplier_tax_id` and `customer_tax_id` as
separate roles, phrased by role rather than by printed label ("the party who
ISSUED and is owed" versus "the party BILLED, who owes"), so the compiled prompt
asks for both. `customer_tax_id` rides `ExtractedInvoiceFields` and
`ExtractedFieldAnchors`, grounded through the same tax-id validator and carried
into the draft with its own provenance envelope.

The cross-side fallback in the counterparty selection is deleted. An ISSUED
document takes the customer side, a RECEIVED document takes the supplier side,
and neither falls back to the other. A counterparty the reader could not recover
stays `None` and is refused as a missing field naming the override that supplies
it.

The gate is `application/ledger/tests/test_counterparty_side_selection.py`, five
cases, 310 lines, landed at `5233cce149` and re-run at 5 passed sequentially on a
cold cache.

## The premise this Step was opened on was wrong

The row originally asserted that an ISSUED invoice could name the filer as its
own counterparty in the Modelo 347 and 349 totals AEAT reconciles against the
other party's declaration. That harm does not reach those totals today. Two
landed guards refuse it: one catches the filer appearing as its own
counterparty, the other catches the mirror mis-direction.

Both guards load the taxpayer profile, and both document their own hole: a bucket
whose profile is absent or carries no tax id cannot be checked, so the guard
returns without refusing. That is a defensible guard-design choice — a guard that
cannot run must not block a path it cannot judge — and it is the wrong thing to
be the only line of defence for a filing-grade identity.

The correction matters beyond this row. Had the gate been written against the
original premise and exercised on a normally configured bucket, it would have
passed on arrival: green because of a guard its author did not write. That is the
mirror of a red arriving from a production guard rather than from the assertion
under test, and it is harder to notice, because a red prompts investigation while
a green from the neighbourhood is indistinguishable from success.

## The lane was not manual, it was closed

The mutation that restored the fallback reddened two cases. The first is the
load-bearing one: with the fallback present the issuer is silently substituted
and no refusal occurs.

The second was not sought and is the more consequential finding. With a wrongly
extracted supplier in hand, the agreement check compares the operator's correct
`--counterparty-nif` against it, the two disagree, and the operator's correct
value is refused. On a bucket with no profile the fallback blocked the documented
workaround; on a bucket with one, the guard blocked the confirm. Either way the
ISSUED path had no working route, so the earlier characterisation of that lane as
"effectively manual" was wrong: the manual remedy every refusal message points at
did not function for the case that most needed it. The fix opens a closed path
rather than automating a manual one.

## The suite had been running in the blind configuration all along

The default runtime-profile fixture writes no taxpayer profile, so every
pre-existing confirm test exercised the fallback with both guards inert, and none
of them looked at the selection. The blind spot was not that the guards masked
the defect; nothing watched the selection at all.

The gate therefore asserts its own premise: one case proves the active-profile
load raises in the same fixture the others use, so adding a profile to that
fixture makes the gate say so rather than silently beginning to measure the
guards instead of the selection logic.

## The first mutation attempt lied

The runtime form returned fully green under mutation, which is the tell that the
patch never landed rather than evidence the gate is sound. Two mechanical causes:
pydantic caches whether a model declares `model_post_init` at class creation, so
patching the attribute afterwards changes nothing; and the confirm path holds an
already-imported draft class, so swapping the module attribute misses it.

It was caught because the probe asserts an observable change before trusting the
run. The source-edit window that replaced it held the original bytes in memory,
applied its mutation through an anchor that refused to fire on zero matches — it
did refuse once, on a line-ending mismatch — and verified restoration by digest in
a `finally`. The target file was byte-identical afterwards.

### The runtime form was not the problem; the seam was

An independent re-verification lands the same mutation at runtime, so the
conclusion above should not be generalised into "mutate this code by editing the
source". Both mechanical causes are properties of the seam that was chosen, not
of runtime patching: reassigning a plain class attribute loses to the instance
`__dict__` pydantic v2 stores field values in, and swapping a module attribute
misses a class the confirm path already imported.

A `property` installed on `InvoiceDraft.customer_tax_id` and `customer_name`
sidesteps both. A property is a data descriptor, so it wins over the instance
`__dict__` on the class object the confirm path is already holding, and it
intercepts exactly the two attribute reads the selection performs. Serialization
reads `__dict__` directly and is untouched, which makes the patch as narrow as
the fallback it restores rather than a class-wide rewrite that could red
something else and be mistaken for a proof.

This matters beyond one Step. A source-edit window is shippable state in a tree
where peers commit continuously, and it was reached for here on the belief that
runtime patching could not work. It could; the first attempt had simply gripped
the wrong seam.

## How this code reached main

The implementation landed accidentally, swept into a 101-file bare commit while
the lane was still mid-implementation with no verification run. That commit took
the source half and left the fixture half uncommitted, redding three parity
gates; consistency was restored in an eight-line explicit-pathspec commit.

The failure mode is worth recording because no author caused it. A commit with no
pathspec is not "commit my work", it is a decision — made by someone with no
knowledge of the change — about where to cut somebody else's atomic unit. It was
found by an empty `git diff` on files whose edits were plainly on disk, because
the working-tree content had become HEAD.

## Why this is upstream of classification

The deterministic classifier consumes the resolved counterparty identity and an
establishment signal to derive the IVA category. While the readers could not tell
the two printed parties apart on an issued document, that establishment signal
was unreliable exactly where reverse-charge classification depends on it. This
Step is therefore a precondition for classifying foreign and reverse-charge
invoices, not only a confirm-path correction.

The structured reader is the one path that can already distinguish both parties.
It remains separately unable to stamp provenance — no production site constructs
an exact-structured field origin — and that gap is untouched here and still
unowned.

## Verification

Gate: 5 passed, sequential, cold cache. Mutation: fallback restored, 2 failed and
3 passed, both reds inside the gate's own assertions on a bucket with no profile
tax id, so the two profile guards were inert and could not have produced them.
Confirm surface: 11 passed in isolation; a full-directory run required sequential
re-execution to clear concurrent registry writes, as the local-execution rule
predicts. No failure in the directory was attributable to this change.

Re-verified independently, sequentially, with the cache provider disabled, by a
second lane that reproduced the figures rather than accepting them.

The gate reproduces at 5 passed. The mutation reproduces at 2 failed and 3
passed, through the runtime seam described above, with the observable delta
printed before any assertion ran. Both reds were located rather than merely
counted. The first is the load-bearing one: `pytest.raises` in the gate body
recorded DID NOT RAISE, and the run log shows the confirm went on to write the
catalogue entry — the defect performing itself. The second is a production
refusal raised inside the confirm path under test, not in fixture setup, when the
agreement check found the operator's correct override disagreeing with the
fallback-supplied issuer. Neither red came from the two profile guards: the log
records the profile resolution returning no record twice on the refusal case,
which is those guards loading a profile that is not there and returning without
judging. That is the inertness premise observed at runtime rather than asserted
from a docstring.

The directory result the earlier record left open: the whole of
`application/ledger` runs 742 passed and 4 failed on the `unit` lane, and 19
passed on the complement, both sequential. All four failures are the same
`regime_legend` field on the draft-projection parity and provenance cases, which
belongs to a different lane's in-flight work and is unrelated to the selection.
Nothing else in the directory depended on the deleted fallback — the concern that
removing it would strand an existing expectation does not materialise.
