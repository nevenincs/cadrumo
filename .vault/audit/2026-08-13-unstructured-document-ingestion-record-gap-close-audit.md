---
tags:
  - '#audit'
  - '#unstructured-document-ingestion'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:f296662321910d70fbb9a264dd1f578b0df120deb0c4692f9db3a555d5bd2a1e'
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

`W09.P17.S92`, `W09.P17.S183`, `W09.P17.S267`, `W09.P17.S269`, and the
claim-level halves of `W07.P15.S57` and `W09.P17.S176`.

The surface each names exists -- the extract and confirm CLI suites ship, the
redaction rules and their enrolment gate ship -- but each row asserts something
*sharper* than existence: that a specific envelope carries provenance end to end,
that a naming convention holds across a suite, that one rule stopped matching UTC
timestamps, that a near-miss identity ruling was taken and applied. Establishing
those needs reading the assertions, not locating the file.

**Classification: unverified.** Recorded as unverified rather than assumed
delivered, because a generic match over hundreds of files is not evidence and
reporting it as such is exactly the shape the swarm-audit rule warns about --
examining part of a corpus and reporting success over the whole of it.

## What this says about readiness

The plan is **substantively complete and bibliographically incomplete**. No row
in any of the three findings turned out to be unbuilt. The gap is that 34
closures were taken without the artefact that distinguishes the three completion
states, and the six in Finding 3 are the population where that distinction still
cannot be made from the record.

The cluster is diagnostic: 20 of the 34 sit in `W09.P17`, the campaign's final
phase, and several say in their own text that they landed by a peer lane. This is
what record discipline looks like when it decays -- late, under parallel
delivery, in the phase where rows were being opened and closed fastest.

## Actions

- The six Finding 3 rows are the only open work this audit creates. Each needs
  its claim read against its tests, and either a record or a correction.
- The eight Finding 1 rows need no verification. If their prose is ever wanted in
  the exec trail it can be lifted from the plan verbatim, but it is not lost.
- Nothing here justifies reopening a closed row. The rows are closed correctly;
  it is the evidence trail that was thin.
