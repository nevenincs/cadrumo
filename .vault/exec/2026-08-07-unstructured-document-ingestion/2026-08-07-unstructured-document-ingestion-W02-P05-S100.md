---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:b9b8700aa77bde4cd40431417cb330380c1e6dacae2d29a9e21276a22b118c74'
step_id: 'S100'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Carry the counterparty taxable-person status as evidence derived from the printed identifier, and consume the taxpayer's censo-registered regime facts from the profile authority

## Scope

- `src/cadrumo/llm`
- `src/cadrumo/application/ledger`

## Description

- Add the classifier input envelope the Step names, with every fact stating its
  own source.
- Derive the counterparty's taxable-person status from the printed identifier,
  anchored to that printed form.
- Resolve absence to unknown structurally rather than by default.
- Take the filer's censo-registered IVA regime from the profile authority, with
  no anchor and a named authority.
- Refuse, in both directions, a fact backed the wrong way for its source.

## Outcome

**The decision that matters is one this Step refuses to make.** A printed VAT
identifier is not promoted to `CustomerTaxStatus.B2B_IVA_REGISTERED`, and that
is a legal constraint rather than a conservative preference. That value is the
trigger for the intra-community supply rule, which classifies the operation
EXEMPT under LIVA art. 25 — and that exemption requires the customer's VAT
identification number to be *verified as valid*, which is what a VIES
consultation does and what this pipeline deliberately does not consult.
Inferring registration from a number printed on a page would let an unverified
identifier zero-rate a sale that may well be taxable: under-declaration
produced by accepting a proxy in place of an authority.

So the envelope carries what a printed identifier actually establishes —
someone printing a VAT identifier is acting as a taxable person — and leaves
"registered" to whoever lands VIES or an operator assertion.

**Absence cannot become a consumer verdict, structurally.** The taxonomy has no
`CONSUMER` member, so no branch and no future edit can conclude one from a
document. That is stronger than a default that happens to be safe: a factura
simplificada legitimately prints no recipient at all, so reading absence as
evidence *about the recipient* would silently reclassify that entire legitimate
population.

**Two sources, and they are not interchangeable.** Document evidence is
anchorable — it was printed, so an operator can be pointed at the printed form.
A profile fact is authoritative and unanchorable — the filer's censo regime is
true whichever document is being classified, so there is no phrase on the page
to highlight. The envelope refuses an anchor on a profile fact and refuses an
authority on document evidence, because either direction makes it lie about
where an auditor should go and look.

Absent a resolvable profile, no regime fact is recorded at all rather than a
default being assumed: guessing the filer's regime would change the tax on
every document they file.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_classifier_inputs.py -m unit -n0 -p no:randomly
    12 passed in 1.09s

Twelve collected, twelve ran, none deselected.

Four mutations from a plugin outside the repository:

    absence_means_consumer        -> 2 failed, 10 passed
    regime_defaults_to_general    -> 1 failed, 11 passed
    profile_fact_claims_an_anchor -> 2 failed, 10 passed
    drop_the_anchor               -> 1 failed, 11 passed

The first mutation is worth describing, because writing it exposed how the
defence actually works. There is no way to mutate the code into reporting
"consumer", since the taxonomy carries no such member — the structural defence
holds against the mutation itself. The reachable mutation is to invert the
verdict, which reddens both the absent case and its positive control. A gate
whose defect class cannot be expressed is a better outcome than one that merely
catches it, and the mutation attempt is what demonstrated the difference.

## Notes

**Three of the four files this Step would naturally have edited were live peer
WIP**, so it was built as new modules instead. `core/_field_origin.py` was
mid-flight gaining a `DERIVED` member that is not in HEAD, and
`_evidence_draft.py` was carrying +31 lines with a new provenance test beside
it — that is the same provenance mechanism this Step would have extended, being
written at the same moment.

Routing around it produced a better design than contending would have.
`FieldOrigin`'s own docstring scopes it to "how one field's value was obtained
**from a source document**", and every member names a way of reading a page. A
censo-registered regime is not read from the page at all, so recording it under
a document-reading origin would have contradicted that enum's stated contract
to make one fewer file. The separate source axis says the true thing instead.

**The index was busy with another lane's staged work at three attempts**, and a
bare commit takes the whole index. An earlier apply-cached attempt found that
index holding `dev/locales` files and two registry TOMLs whose staged diff
*deleted* recargo casilla rows — exactly the content that must not be swept into
someone else's commit message. That patch was reversed at once and the peer's
index confirmed intact. The Step landed on a later attempt when the index was
free, guarded so it would skip rather than swallow.

**One near-miss worth recording.** The commit's own `--numstat` showed only
three files; the new core module was absent, which would have meant HEAD
importing a module that was not in it — a broken tree. It was not broken: a
peer's sweep had already committed that file minutes earlier, so it was in HEAD
under `b4657b303a` rather than missing. Verifying rather than reasoning is what
separated those two readings, and they look identical in a numstat. HEAD was
exported and re-run to confirm: the envelope imports and the suite is **12
passed** against committed content alone.

VIES is untouched. No network authority was added, no model was loaded, pulled,
or contacted.
