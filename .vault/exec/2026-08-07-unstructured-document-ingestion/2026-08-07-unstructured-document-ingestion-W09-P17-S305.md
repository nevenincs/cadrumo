---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:2af5fbe1c823f746c91988c9c0cf7afe4a497b6adb77d6e3a3f9b8f5ceec9b9b'
step_id: 'S305'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# MEASURE, do not sweep, whether the sibling advisories can be grounded the way the agrario one now is. The advisory added typed legal and source refs read off the registry casilla and its binding, minting nothing, because the ruling forbade the prose form that every other advisory in this tree uses. That leaves the correct instance in the MINORITY, and an inconsistency where the right shape is outnumbered decays toward the majority. The deliverable is the measurement rather than the conversion. Count the advisories restating an article in prose, and for each establish the question that actually matters: whether its refs are RESOLVABLE from the registry at all, or were hand-written because no binding or casilla carries them. Those two populations need opposite treatments. A prose ref with a registry-resolvable equivalent is a mechanical conversion. A prose ref with NO registry-resolvable equivalent is an advisory asserting a provision the registry cannot corroborate, which is a grounding gap wearing the costume of a style inconsistency and must be escalated rather than converted. Report the split before proposing either

## Scope

- `src/cadrumo/application`

## Description

- Scan every advisory module for typed grounding against prose provision
  restatement, counting docstring citations as documentation rather than as a
  claim the advisory makes to an operator.
- Split the prose population by whether a registry entity is in scope for a
  typed ref to be read off at all.
- Report the split. Convert nothing.

## Outcome

MEASURED, and the row's motivating premise is FALSE at HEAD.

Twenty-two advisory modules across the application layer and one registry
validator. The split:

* NINE carry typed grounding attached to what they emit -- the agrario one
  plus art. 20, art. 52, attribution-received, autonomic deducción, both DT12
  advisories, the M210 convenio LOB one and objective estimation.
* SEVEN restate a provision in prose with no typed refs.
* SIX cite no provision either way, so there is nothing to ground: the country
  vocabulary, ledger evidence, official box, rate box, settlement grade, and
  the cross-revision registry validator.

So the correct shape is NOT in the minority. Among advisories that cite a
provision at all it is nine against seven, which inverts the row's concern
that an inconsistency where the right shape is outnumbered decays toward the
majority. The agrario advisory joined a majority rather than founding one.

THE SPLIT THE ROW ASKED FOR, which is the part that decides treatment. Of the
seven prose advisories, five sit on a registry surface -- a casilla, a binding
or a snapshot is in scope, so an equivalent typed ref is plausibly resolvable
and the conversion is mechanical: mínimo descendientes, prior payment,
prorrata regularización, operator override, bienes de inversión.

TWO have NO registry entity in scope, and they are the escalation the row
predicted: retención rate, and the aggregation evidence advisory. The first is
the one that matters. It cites LIRPF art. 101, art. 80, art. 95, Ley 35/2006
and RD 439/2007 while reaching no registry surface at all -- and retención
rates ARE registry data, resolved for the filing year and period by the prompt
compiler elsewhere in this same campaign. An advisory asserting those
provisions with no registry entity to corroborate them is a grounding gap
wearing the costume of a style inconsistency, which is exactly the shape the
row said must be escalated rather than converted.

Nothing was converted. The deliverable was the measurement and the split.

## Notes

STATED METHOD, so the counts can be re-derived rather than trusted. Typed
grounding was detected by the presence of legal_refs or source_refs in the
module; prose provisions by an article/disposición/Ley/RD pattern over CODE
string literals only, with docstrings excluded deliberately -- a docstring
citing an article documents the author's reasoning, while a code literal is
text an operator is shown, and only the second is a claim the advisory makes.

The registry-surface split is a PROXY and is reported as one: it counts
references to casilla, binding, snapshot and revision names in the module. It
answers "is a registry entity in scope here" and not "does that entity carry
refs for this provision". The five mechanical candidates therefore need
confirming one at a time before conversion; the two escalations need no such
confirmation, because zero registry surface is decisive on its own.
