---
tags:
  - '#exec'
  - '#iva-service-localisation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:a04d7f80bb933155653376f08af16e68f0de0b434d88b417e4aed665c6e8b278'
step_id: 'S06'
related:
  - "[[2026-08-12-iva-service-localisation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace iva-service-localisation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-08-12-iva-service-localisation-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Sweep the consumers of the outbound services row for the widened outcome: any caller, projection, advisory or Modelo 303 routing that assumed an ES-to-outside-the-Comunidad service is always not-subject. Run the full IVA and ledger suites sequentially and triage owner failures from peer churn before closing. Record the art 69.Dos list as a named carry-forward in the exec record - its population is over-taxed by default, which is the direction nothing in the apparatus watches and ## Scope

- `src/cadrumo/domain/iva/`
- `src/cadrumo/application/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Sweep the consumers of the outbound services row for the widened outcome: any caller, projection, advisory or Modelo 303 routing that assumed an ES-to-outside-the-Comunidad service is always not-subject. Run the full IVA and ledger suites sequentially and triage owner failures from peer churn before closing. Record the art 69.Dos list as a named carry-forward in the exec record - its population is over-taxed by default, which is the direction nothing in the apparatus watches

## Scope

- `src/cadrumo/domain/iva/`
- `src/cadrumo/application/`

## Description

- Swept every production consumer of the not-subject category and of the
  general-services kind for an assumption that an outbound service always falls
  outside Spanish IVA.
- Swept the rule id across the tree: the decision table, the place-of-supply
  registry row, and the manual oracle, which resolves whatever id a result
  carries rather than pinning one.
- Ran the IVA domain and ledger suites sequentially, to a log read back from
  disk.
- Triaged every failure against the feature surface before closing.

## Outcome

Done. 2099 pass, 13 fail, and all thirteen are outside this feature's surface.

**The sweep found no consumer to change.** Nothing in production reads the
not-subject category as "an outbound service", and nothing keys on the rule id:
the category feeds the component table, the saturation reasons and a description
map generically, and the manual oracle resolves whatever id a result carries.
The one place that names the general-services kind is the producer's
nature-to-kind map, which the rate-tier widening already went through.

**Owner triage of the thirteen.** Eight are one peer cause: an `IvaCategory`
member shipped without its component rows, its saturation reason or its entry in
the named-member list, so the parity cases over the catalogue fail. One more is
that member's neighbour -- an intra-community reason's wording moved under other
work. Four are in the ledger and share a signature this record states plainly
because it is the tell: the assertions fail against an EMPTY string, which is
locale rendering in flight rather than a behaviour change, plus one missing
payload key.

None of the thirteen touches classification, supply nature or the
place-of-supply table, and the working tree is clean for every file they live
in, so they are failing on committed peer state rather than on anything here.

## Notes

**The carry-forward, named as the row required rather than left to be found.**
Art. 69.Dos is not modelled, so its closed list of B2C services to recipients
outside the Comunidad now classifies as subject and is over-taxed by default.
The project's own mandate says this is the unwatched direction: over-payment
produces valid output, no refusal, and no signal to the taxpayer. It is chosen
here only because an operator can see and correct a subject classification,
while the under-declaration it replaces was silent in both directions.

Closing it needs an axis that does not exist. `TransactionKind` carries one
general services member, so attaching the lettered list would mean deciding
which item an invoice falls under from its own prose -- the rule-table-as-model
this domain refuses by name. The honest next move is a service-kind vocabulary
grounded in the article's own enumeration, which is its own change.

**Second carry-forward:** `PUBLIC_ADMINISTRATION` reaches neither limb and lands
on human review. Art. 69.Tres.4.º treats a legal person holding an IVA
identification as an empresario for these rules even when it does not act as
one, and that is a ruling with its own grounding rather than a default anyone
should pick.

**Honesty pass, run against this record after closing and sharpening the
carry-forward rather than confirming it.** The gap is wider than "art. 69.Dos's
list", and the wider statement is the one a later reader needs.

Art. 70's *reglas especiales* override art. 69 and several of them are B2C
rules. This feature is insulated from most of them by construction: the two rows
key on `SERVICES_GENERAL`, and land-related, passenger-transport and restaurant
supplies are their own `TransactionKind` members that these rows never match.
That insulation is only as good as the kind the operator picks.

The population it does NOT insulate is electronically supplied services. The
bundled art. 69.Dos list runs a) to l) and names no e-services item -- it stops
at the gas and electricity networks and goes straight to "Tres. A efectos de
esta Ley" -- so an outbound B2C e-service recorded as `SERVICES_GENERAL` now
reaches the subject branch. Whether that is right turns on art. 70.Uno.4.º and
on art. 70.Dos's *uso efectivo* clause, which this pass did not settle and which
the missing service-kind axis is what would let anyone settle. The bundled
corpus's own vintage is under separate work, which is a second reason not to
rule on it here.

The disposition stands unchanged and is stated deliberately rather than by
default: over-taxing a population an operator can see and correct beats
relieving one silently. But "art. 69.Dos is unmodelled" understated it, and the
next change on this axis should read art. 70's B2C rules alongside 69.Dos rather
than only the lettered list.
