---
tags:
  - '#audit'
  - '#unstructured-document-ingestion'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:5c33603b2d28956e507fdb89964f3b8216eee68e64ed7bd29f358d50ae92c340'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# `unstructured-document-ingestion` audit: `thirty-four closed steps with no execution record`

## Scope

The plan reports 306 of 306 steps closed with no open row. Cross-checking every
step identifier against `.vault/exec/` finds **274 records for 306 steps**: 34
closures carry no execution record.

The governing rule is explicit that this is not cosmetic -- no step is complete
without a matching exec record or a close audit recording the carry-forward,
*otherwise delivered-as-specified, delivered-narrower and
recorded-but-not-implemented wear the same checkbox*. This audit is that close
audit. It classifies all 34 against the tree at HEAD and states, per row, which
of the three it is.

**It is a verification pass, not a reconstruction.** Writing 34 records after
the fact would imply a contemporaneous account nobody has. What can honestly be
established now is whether the deliverable exists, and that is what is recorded.

## Finding 1 -- eight rows carry their own account in the row text

`W02.P05.S222`, `W02.P05.S247`, `W09.P17.S148`, `W09.P17.S167`,
`W09.P17.S239`, `W09.P17.S240`, `W09.P17.S323`, `W09.P17.S326`.

Each opens with its own verdict -- DELIVERED, RETRACTED, RULED and REWORDED,
DONE, *Decision taken*, *Both premises this row was opened on are false* -- and
then gives the reasoning a record would have carried. Four are outright
reversals of the row's own premise, which is the most valuable thing a record can
say and the easiest to lose.

**Classification: delivered, account present, container wrong.** The content that
belongs in a record was written into the plan instead. That is a real defect --
the plan is a work list and a record is evidence, and prose in the wrong one is
not discoverable from the exec trail -- but nothing is missing.

## Finding 2 -- twenty rows verified against a named artefact at HEAD

Each names a concrete surface, and each surface is present:

- `W01.P03.S07` -- `retencion_rate`, `retencion_amount`, `suplidos_amount` and
  `discrepancies` are fields on the draft; the direction answer is stamped as a
  SUGGESTION. **Vocabulary drift**: the row's *transcription content address*
  ships as an evidence content hash, not under that name.
- `W02.P05.S15` / `S16` -- the `supports_images` capability boundary spans the
  provider adapters; the Anthropic adapter is present. Both rows say they landed
  by the peer lane, which is why no record followed.
- `W02.P07.S237` -- its deliverable WAS the missing `W02.P07.S205` record, and
  **that record exists**. The row is a record-about-a-record whose output is on
  disk.
- `W07.P15.S57` -- the optional-dependency split is present at the MCP entry
  point.
- `W08.P16.S85` -- the per-file statement-folder guard is present.
- `W09.P17.S84` -- the waist accounting drives the attachment store.
- `W09.P17.S113` -- **verified by its own gate**:
  `test_no_production_module_hand_formats_a_provenance_stamp` ships, which is
  precisely the singularity the row asked for.
- `W09.P17.S122` -- the territory mapping is in the registry authoring tree.
- `W09.P17.S136`, `S140`, `S152`, `S160` -- the establishment ladder, the filer
  establishment module and the confirm path are present.
- `W09.P17.S168` -- the rate-tier demand is a single shared predicate.
- `W09.P17.S170`, `S179` -- the country vocabulary and its specimens are present.
- `W09.P17.S171` -- the two-fact party split (`PartyFact`) is present and was
  exercised directly by later work on this surface.
- `W09.P17.S176` -- `evaluate_anchor` is present with its regression suite.
- `W09.P17.S177` -- text-node grounding is present in the parser and the draft.
- `W09.P17.S180` -- the overseas-address omission is present.
- `W09.P17.S262` -- the Facturae InvoiceTotals composition is a bundled corpus
  artefact carrying its own provenance.
- `W09.P17.S290` -- the field-grounding modules are present.

**Classification: delivered as specified, record absent.** One qualification:
`S07` is delivered with the vocabulary moved, which is the difference between
delivered-as-specified and delivered-narrower that this audit exists to make
visible. Nothing about it is narrower; the names simply drifted.

## Finding 3 -- six rows are verified only to surface level, not to claim level

**RESOLVED. All six were read against their assertions, and all six are
delivered.** This section originally recorded them as unverified because a
generic match over hundreds of files is not evidence. Reading the claims instead
of locating the files settles every one, and two of them turned out to be
delivered MORE completely than the row asked.

- `W07.P15.S57` -- `test_tabular_extra_split.py` carries both sides the row
  demanded: a known fixed-layout file importing fully without the extra, and an
  unknown vocabulary refusing at the mapping call and naming the extra. It also
  carries a third case the row did not ask for, proving the refusal is caused by
  the extra's ABSENCE rather than by the file -- the anti-tautology control that
  makes the other two mean anything.
- `W09.P17.S92` -- `test_evidence_provenance_reaches_the_operator.py` drives
  extract and confirm end to end and asserts the envelope carries both
  provenance and discrepancies, including an arithmetic disagreement reaching
  the extract envelope and a self-contradicting document refused at confirm.
  That is reachability, which is what the row said the hand-built parity gate
  could not establish.
- `W09.P17.S176` -- delivered on BOTH limbs the row offered as alternatives, not
  one. `_evaluate_anchor_against` takes a `derive` callable and resolves
  `CONTRADICTED` when the re-derivation disagrees with the value; and the
  structured path RAISES when a caller supplies an explicit anchor for a textual
  value with no derivation, with a message naming the exact hazard the row
  described -- an envelope asserting the record evidences one value on the
  strength of a different string occurring in it. **This entry corrects a
  mid-verification reading of my own**: on the public signature alone the refusal
  leg appears absent, and only reading the structured caller shows it is there.
- `W09.P17.S183` -- the `asserted_gap` prefix is carried in test NAMES across the
  ledger suites, which is exactly the countable, greppable form the row asked
  for in place of a docstring convention.
- `W09.P17.S267` -- `_ISO_INSTANT_RE`, `_timestamp_spans` and
  `_outside_timestamps` ship, and the module's own comment restates the defect
  the row reported: the seconds and microseconds of a serialised instant are
  seven digits with separators and a trailing letter, and `12345678Z` even
  carries a valid check character, so only the surrounding span can tell the two
  apart.
- `W09.P17.S269` -- the ruling is taken and recorded at the strategy level, as
  the row required. The personal identity is split into two rules by whether a
  separator breaks the span: the unbroken arm hashes a lookalike rather than risk
  missing a mistyped identity, while the separator-bearing arm was carved out on
  measurement after this application's own work-unit names normalised onto the
  identity shape and an operator was handed a path they could not use.

**Classification: delivered as specified, record absent.** No row in the audit
now stands unverified.

## What this says about readiness

The plan is **substantively complete**. All 34 record-less closures were checked
against the tree, and not one turned out to be unbuilt, narrowed, or
recorded-but-not-implemented. Two are delivered beyond what their row asked --
`S57` carries an anti-tautology control nobody demanded, and `S176` implements
both limbs of an either/or.

What is incomplete is the evidence trail, in two places.

**34 of 306 steps closed without an execution record.** The cluster is
diagnostic: 20 sit in `W09.P17`, the campaign's final phase, and several say in
their own text that they landed by a peer lane. This is what record discipline
looks like when it decays -- late, under parallel delivery, in the phase where
rows were opening and closing fastest.

**18 phases and 10 waves closed with zero phase summaries.** No
`*-summary.md` exists anywhere under this feature's exec directory. That is a
separate omission from the missing step records and it is total rather than
partial, which makes it a convention that was never adopted on this campaign
rather than one that lapsed under pressure.

Neither gap is a reason to reopen a row. The rows are closed correctly; the
question the trail could not answer -- which of the three completion states each
closure was -- is answered here, per row, against HEAD.

## Actions

- **No open verification work remains.** Every one of the 34 is classified
  against HEAD, and the six that were unverified at first pass are resolved
  above.
- **AMENDED 2026-08-13: the 34 records were subsequently written, at operator
  direction, and this section originally refused them.** The refusal is left
  standing above rather than deleted, because the reasoning still holds and a
  reader deserves to see what was traded: a record authored now implies a
  contemporaneous account nobody has, and no later reader can distinguish a
  reconstructed record from one written at the time.

  What resolves that objection is not the operator's instruction but the form the
  records take. Each states **in its own Outcome section** that it was
  retrospectively reconstructed on 2026-08-13, that it is NOT a contemporaneous
  account, and that what it records is that the deliverable exists at HEAD and
  how that was established. A reader cannot mistake one for a written-at-the-time
  record, because it says so itself.
- The eight Finding 1 rows point at their own verdict in the plan text, which is
  where their real account lives.
- The absent phase summaries are recorded as a convention gap and are NOT
  retrospectively authored: a summary is a synthesis of records nobody wrote at
  the time, and there is no equivalent honest form for it.
- Carried forward to any future campaign on this surface: a row that closes with
  its verdict written into the plan text is the tell that the record was skipped.
  Eight rows here did it, four of them recording a REVERSAL of their own premise
  -- the most valuable thing a record can carry and the easiest to lose when it
  is filed as a work item instead of as evidence.
