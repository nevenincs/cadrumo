---
tags:
  - '#audit'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:13b2526eb39ebcdc2559f1c0967d7a044d2f7b2c88a6e9dd208413524cae31b7'
related:
  - "[[2026-08-06-llm-package-split-plan]]"
---

# `llm-package-split` close: what the unchecked steps actually are

Thirty of the plan's eighty-three Steps sit unchecked while much of the code they
describe is at HEAD. That gap is the thing this document exists to close, because
an unchecked Step and an undelivered Step look identical from the plan, and the
repo rule that a Step may not be checked without a matching exec record means the
plan cannot be corrected by simply ticking boxes.

Every classification below was made by reading HEAD, not by reading the plan or
recalling the work. Where a Step's stated file path no longer matches where the
work landed, that is called out rather than smoothed over -- the divergence is
information about the campaign, not noise to normalise away.

## A. Delivered and verified at HEAD; the exec record is the only thing missing

Each was confirmed by locating the symbol, the gate, or the absence the Step
demands, at HEAD, in this session.

- `W04.P08.S34`, `S35`, `S36`, `S37` -- the client, the models/errors/pricing
  trio, the provider adapters and the retention function are all gone from
  `adapters/outbound/llm/` and present under `src/cadrumo/llm/`. Verified by
  directory listing on both sides.
- `W04.P08.S38` -- no string owner label or error-registry qualname under
  `core/` still names a vacated `adapters.outbound.llm._*` path. Verified by
  search returning empty, which is the Step's own red condition inverted.
- `W04.P09.S41` -- the cache, run-telemetry and usage stores remain in
  `adapters/outbound/llm/`, which is the Step's requirement rather than
  leftover work. Their staying put is what keeps the diagnostics consumer
  unconditional.
- `W04.P09.S39`, `S42` -- both gates are at HEAD in
  `src/cadrumo/tests/test_llm_classification_division.py`, mutation-proven in
  this session before they landed.
- `W05.P11.S47`, `S50`, `S55` -- the subprocess classifier family, the provider
  and acknowledgement flags, and every declared cloud symbol are absent from
  production, with the MCP call runtime asserted to have survived as the
  positive control.
- `W05.P11.S77`, `S78` -- the superseded ADR carries its narrowing, and the
  provenance-stamp gate asserts every mintable transport is on-host.
- `W02.P04.S56`, `S57` -- emisor and destinatario are mapped by role, and the
  invoice number is read from the document identifier element.
- `W03.P07.S59`, `S62` -- both encrypted stores exist and are wired.
- `W04.P12.S63` -- `SRC_CADRUMO / "llm"` is enumerated in the sensitive-surface
  list.

### `W02.P04.S80` landed somewhere other than where the Step says

The Step names `adapters/inbound/einvoice/`. The rate-slot resolution is in
`application/ledger/_evidence_draft.py`, and a path-scoped search of the stated
directory finds nothing -- which would have read as "not delivered" and produced
a duplicate resolver. A semantic search found it immediately.

The Step is delivered, and closing it in this session surfaced a real defect it
had not covered: the confirm path forks on whether the document printed a cuota,
and the two forks resolved the same percentage through two different functions
raising two different error types. One named the rejected rate and the accepted
set through a localised message; the other was raw English. Which refusal an
operator saw depended on a property of their document unrelated to the rate.
Consolidated onto one promoted resolver, with the 5% pre-2025 case the Step's red
condition names now pinned by test, including a positive control proving the
fixture is otherwise confirmable.

## B. Delivered narrower than written

- `W03.P06.S29` asks for a persistence roundtrip of the interchange payload.
  What exists is a strict save-load-equality roundtrip with every defaultable
  field populated non-default, plus an anti-tautology proof, over the
  **extraction draft** rather than the interchange payload. That is arguably the
  correct target -- the draft is what actually crosses a persistence boundary,
  and the interchange payload is transient -- but it is a narrower claim than the
  Step makes, and the Step should be closed on that reasoning explicitly or
  reopened, not quietly ticked.
- `W01.P02.S72` asks for a per-check record of which of the five secure-storage
  gates scans by whole-tree rglob, which enumerates a fixed list, and which is
  test-side only. The non-vacuity assertion added for `S08` documents this for
  the enumerated gate it guards; the other four are not characterised. Partially
  delivered.

## C. Not delivered

- `W02.P03.S12` -- the read-time media-kind derivation is NOT retired.
  `DocumentShape` was added alongside it and `EvidenceInput` exposes both, but
  `MediaKind` is still branched on at 39 sites across 15 files. The Step's red
  condition -- any caller still branching on the two-member media kind -- is
  currently met.
- `W02.P03.S11` -- the sanitizer's embedded-file walker was not extracted into a
  reusable reader; `adapters/inbound/sanitizer/_dynamic.py` references neither
  taxonomy. The einvoice package grew its own embedded-file iteration instead,
  which means the duplication the Step existed to prevent is the state that
  shipped.
- `W01.P01.S05` -- no test asserts the CLI group degrades to an install-hint
  placeholder when the extra is absent.
- `W01.P01.S66` -- no packaging gate asserts PIL importers rest on a declared
  dependency.

These four are the campaign's real remaining surface. `S11` and `S12` are a pair:
`S12` cannot honestly close while `S11` leaves a second embedded-file walker in
the tree, because the media-kind branch is what the second walker is reached
through.

## D. Blocked across the campaign boundary, by design

`W02.P05.S70`, `S81`, `S83` sequence behind the sibling `invoice-canonical-structure`
lane's writer Step. `S83`'s red condition spans both campaigns deliberately, so
neither can land half of it. Recorded here as a carry-forward with a named
dependency rather than as an open item with no owner.

`W02.P05.S69` and `S71` are the idempotency pair. The keyed derivation
(`derive_keyed_purchase_invoice_evidence_id`) and the `idempotency_key` parameter
are at HEAD; the test half was not confirmed in this pass and is left unchecked
rather than assumed.

## What this means for the campaign's completion claim

The campaign is **not** structurally complete, and the honest figure is that four
Steps are genuinely undelivered, two are delivered narrower than written, three
are cross-campaign carry-forwards, and one pair is unverified. Everything else
named above is delivered and needs only its record.

The failure mode this document guards against is the one the close rule names:
checking a box because the code looks present, which makes "delivered as
specified", "delivered narrower" and "recorded but not implemented" wear the same
mark. Three of the categories above would have been invisible under that
treatment.


## Session outcome (2026-08-07, after this audit was first written)

Four of the items above were closed in the same session that classified them.

`S05` and `S66` were the two "not delivered" items with self-contained scope, and
both turned up something the Step had not anticipated. `S05` assumed an absent
`llm` extra is reachable by installing without it; it is not, because Pillow is
deliberately declared in the BASE dependencies as well, so the extra is nominal
today and its guard is dormant. The absent state has to be constructed with a
meta-path block rather than installed. `S05` also assumed a lazily-loaded
command group with a placeholder to degrade to; the inference verbs have no such
group, and the real mechanism is the verb-level guard, so the test lives with the
guard rather than at the CLI path the Step names.

`S66` produced the sharper result. The gate it asks for -- every module importing
PIL rests on a declared dependency -- cannot see the reliance that motivated it,
because nothing imports PIL by name anywhere in production; the rasteriser
reaches it through `pypdfium2`'s `to_pil()`. An import-statement gate would have
reported the inference path clean while the original defect stood. Pillow is
therefore asserted directly, beside the general scan, and that asymmetry is
recorded in the module rather than papered over.

`S11` was not actionable as written. There is no hand-rolled embedded-file walker
to extract: the sanitiser and the e-invoice probe are both thin uses of pikepdf's
own `Pdf.attachments` mapping, one deleting and one reading. Extracting a shared
walk would have added an indirection over a third-party API that already is the
shared reader. The Step's red condition was the part with substance, and it is
now pinned -- reading a payload must not soften the stripping.

`S72` is closed by recording, per gate, whether it discovers its subject or is
told it. That distinction is what makes a coverage claim about a new directory
checkable, and it is invisible from the gates' names.

### One assertion was written and then withdrawn

The `S11` module briefly asserted that reading an embedded payload leaves the
input bytes unchanged. It passed. It could not have failed: the probe takes
`bytes`, and `bytes` are immutable, so the comparison holds whatever the function
does. It was replaced by the property that can break -- that no file is left on
disk, since pikepdf opens from paths as readily as from buffers and a temp-file
implementation would return the right payload while spilling evidence bytes.
Recorded here because a tautology that survives review is worse than an absent
test, and this one survived writing.

### `W02.P03.S12` remains open, and is the campaign's last coding item

The read-time media-kind derivation is still live at 39 sites across 15 files.
It is not deferred for difficulty: `_evidence_draft.py`, `_evidence_input.py` and
`_llm_classification.py` are all carrying another campaign's uncommitted
media-type work at the time of writing, and a 39-site sweep through them would
collide with a peer mid-edit. The sweep wants a tree where those three files are
quiet.

Note also that `S11` and `S12` were paired in the original reading of this
campaign -- `S12` blocked behind `S11` leaving a second walker in the tree. That
pairing dissolves with the finding above: there is no second walker, so `S12` is
blocked only on peer contention, not on `S11`.

### Standing count

Seventy-six of eighty-three Steps closed. Open: `S12` (coding, contended),
`S29` and `S69`/`S71` (verification of claims not confirmed in this pass), and
`S70`/`S81`/`S83` (cross-campaign carry-forward with a named dependency).

