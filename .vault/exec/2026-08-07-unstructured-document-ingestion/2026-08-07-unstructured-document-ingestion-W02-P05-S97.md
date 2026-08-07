---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:70874cca1d5cae5bceea671926de9eec103832091bddc8af94d4e082e4132eee'
step_id: 'S97'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Derive origin AND destination as anchorable printed evidence, both parties' country prefixes from their printed tax identifiers plus any printed address countries, and where the document states them the shipment or delivery endpoints, which for goods can differ from either party's establishment. The pair sets the IVA treatment for a business invoice, so a single counterparty establishment is insufficient, and the classifier consuming this today has no producer for it at all. Transcribe rather than infer so each value keeps its anchor, and resolve an unstated or unrecognised country to unknown and never to domestic, since a wrong pairing silently converts an intra-community or reverse-charge operation into a domestic one. Gated by fixtures covering a domestic pair, a foreign EU pair, a pair whose shipment endpoints differ from the parties' establishments, and a document stating no country, mutation-proven by defaulting the unknown case to domestic and confirming the gate reds

## Scope

- `src/cadrumo/llm`
- `src/cadrumo/application/ledger`

## Description

- Establish that both parties' tax identifiers are already transcribed, so the
  country prefix each carries is existing printed evidence rather than a field to
  add. A second home for the same evidence was the first design considered and
  was rejected on that ground.
- Add the deterministic resolver turning one printed country code into the closed
  territorial scope the classifier consumes, or into nothing, derived from the
  Member State catalogue rather than a hand-listed set.
- Model absence as ``None`` rather than as a new enum member, so a missing scope
  is not itself a kind of scope and every consumer's rule table stays unchanged.
- Gate the refusal from several directions and prove it by mutation in both:
  resolving the unknown case to the domestic scope, and refusing every input.

## Outcome

The resolver answers where the printed evidence is decisive and refuses where it
is not, and it never returns a Spanish scope at all. That last property is
stronger than the row asked for, and it is not caution -- it is the substantive
finding of this Step.

**A country code cannot establish the Spanish territory.** ``ES`` names the
Member State, and Spain holds three IVA territories the law treats differently:
the peninsula and Balearics inside the territorio de aplicación del impuesto, the
Canary Islands under IGIC, and Ceuta and Melilla under IPSI, the latter two
outside LIVA entirely. Resolving a Spanish prefix to the mainland would place
every Canarian and Ceutan party inside a territory their operations are not
subject to. That is precisely the restrictive-default shape the row exists to
prevent, arriving one layer earlier than expected: not "unknown treated as
domestic", but "domestic treated as one specific domestic territory". So the
honest reading of a Spanish prefix is "Spain, territory undetermined", and the
honest return is nothing.

The consequence is worth stating plainly rather than leaving to be discovered:
for a domestic invoice between two Spanish parties, this resolver returns nothing
for both, and the establishment axis contributes no signal. Discriminating the
Spanish territories needs sub-national printed evidence -- an address province or
postal code -- which this Step does not transcribe.

A malformed or absent code resolves to nothing rather than raising. Unreadable
evidence is a normal outcome of reading a document a supplier chose the layout
of, not an error condition, so the shape is checked before the core jurisdiction
validator is consulted and that validator remains the single authority on what a
well-formed code is without an exception carrying ordinary control flow.

## Verification

    pytest src/cadrumo/domain/iva/tests/test_establishment.py -n0 -p no:randomly -q
    25 passed in 2.41s

    pytest src/cadrumo/domain/iva/tests/test_establishment.py src/cadrumo/llm/tests/test_regime_legend_vocabulary.py -n0 -p no:randomly -q
    47 passed in 43.84s

Sequential, cold interpreter. A pure function over strings: no model, no network,
no fixture.

Proven by mutation in both directions, each applied to an isolated export so no
tracked file changed.

Resolving the Spanish code to the mainland scope:

    6 failed, 19 passed in 8.00s

Among them the whole-input-space property, which asserts over every Member State
code, a spread of third countries and every malformed shape at once rather than
over a sample.

Refusing every input:

    11 failed, 14 passed in 5.30s

That second one is the necessary counterweight: without it, a resolver that
returned nothing for everything would satisfy every refusal assertion in the
file.

## Notes

This Step is NOT complete and the row stays open. What landed is the derivation;
what remains is the transcription the widened row calls for -- both parties'
printed address countries, and the shipment or delivery endpoints where the
document states them. Those are new fields on the field contract, the response
and anchor schemas, the grounding assembly, the draft and its projection payload.

They were deliberately not started here. That set has to land atomically, because
a declared field with no populating consumer reds the parity gates for every lane
in the tree -- demonstrated twice already in this campaign, once at real cost.
The draft module those fields must reach is currently carrying another lane's
uncommitted foreign-currency work, so an atomic landing was not available.

The place-of-supply mapping that turns a resolved pair into an IVA treatment is a
separate row and was not attempted. A mapping asserted from reasoning rather than
grounded in the bundled corpus would produce a plausible treatment for every
foreign invoice and be wrong only against the counterparty's own declaration,
which is the most expensive shape of wrong available in this chain.
