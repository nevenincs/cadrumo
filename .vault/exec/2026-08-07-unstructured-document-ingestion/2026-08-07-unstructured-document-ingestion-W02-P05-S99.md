---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:aef82f5cab03f6b29bebf048051041e4ec5319a39d9dcfa335b2e84690a31053'
step_id: 'S99'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## What changed

The nature of a supply -- goods or services -- becomes a first-class axis in the
IVA domain, as `SupplyNature` with exactly two members and no `UNKNOWN`. Not
knowing is a property of a derivation, carried by `SupplyNatureDerivation`'s
absent outcome, rather than a third kind of supply: a member meaning "we could
not tell" is storable, and once stored it is indistinguishable from a fact at
every later reader.

One derivation is sanctioned. `STATUTORY_CITATIONS` maps a printed LIVA article
to what citing it establishes, and `derive_supply_nature_from_citation` reads it.
Nothing else derives. There is no rule table over free-prose line descriptions,
and two cases in the gate exist to keep it that way: sentences a keyword table
would map confidently ("Servicios de consultoría informática", "Suministro de
material de oficina") must both leave the axis absent.

`supply_nature_is_required` is the whole of the demand, in one place so two call
sites cannot answer it differently. It returns false for the six domestic
categories settled by their rate tier, true for the cross-border members and the
domestic reverse charge, and true for a category not yet established.

## The namespace guard is the load-bearing part

A bare article number names an article of some statute, not of this one. This
repository bundles both Ley 37/1992 art. 21 -- an IVA export exemption for goods
-- and Ley 27/2014 art. 21, a corporate-income provision. Reading `art. 21` out
of context returns a confident answer from the wrong law, and nothing downstream
can tell that answer from a right one.

So a match requires two things together: an article reference for a declared
number, and a token identifying the IVA law somewhere in the same text. The
qualifier is what keeps the axis inside its own namespace, and it has its own
mutation below.

## Two rows establish nothing, and that is a finding about the statute

LIVA art. 84 fixes who the taxable person is, and its own first paragraph reaches
"las entregas de bienes o presten los servicios" -- both limbs. Citing a reverse
charge therefore says nothing about which was supplied. Art. 163 unvicies is the
Union scheme and likewise covers "presten servicios" alongside "ventas a
distancia intracomunitarias de bienes".

The second was going to be a mistake. The existing kind-of-supply enum documents
art. 163 unvicies as the intra-community distance sale of goods, which is one of
its two limbs; a row written from that docstring would have established GOODS.
Reading the bundled consolidated text refuted it. Both articles are carried as
rows establishing `None` rather than omitted, because a caller finding no row
cannot distinguish "this article does not fix the nature" from "nobody has added
this article yet".

## What the table cannot do yet

The general place-of-supply articles -- LIVA arts. 68 for goods, 69 and 70 for
services -- are absent from the bundled corpus, confirmed by listing what ships
rather than taken from the brief. No row asserts what they establish, because a
row without the text to check it against is exactly the fabricated grounding this
codebase refuses. They are added when the corpus carries them.

The consequence bounds the axis honestly: the articles present reach the
exemption and special-regime citations, which is the population RD 1619/2012 art.
6.1.j obliges to print a reference at all. An ordinary cross-border invoice
citing nothing derives nothing and asks the operator. That is the designed
outcome, not a failure.

## Why no new extracted field

The reading contract was not widened. The citation is already anchorable printed
evidence in the text the reader transcribes, and art. 6.1.j is the obligation
that puts it there. The printed-mention vocabulary documents in its own source
that it cannot serve this axis -- art. 6.1.j fixes no phrase, so an exempt invoice
prints whichever article applies and there is no canonical string to match. This
module reads what it prints instead, which completes a stated gap rather than
opening a second authority beside it. It also avoids widening a single-declaration
surface another lane holds.

## Verification

Gate: 31 passed, sequential, cache provider disabled, marker `unit`.

Every row is checked against the bundled consolidated text the row itself names,
not against a literal typed beside it. An expectation copied from the row under
test would pass whatever the row said; reading the corpus can fail when the row is
wrong about the statute, which is the only version worth running. That check bit
during development: the art. 163 quinvicies row failed because the goods
vocabulary did not cover "ventas a distancia de bienes importados", and the fix
was to widen the statute's own vocabulary rather than exempt the row.

Two mutations, both from outside the repository, both landed at module scope in a
lane-named plugin. Defaulting the unknown case to a supply nature returned 3
failed and 28 passed; dropping the namespace qualifier returned 1 failed and 30
passed, reddening exactly the guard it targets and nothing else. Every red is an
`AssertionError` at a named line in the gate, none from a model validator and none
from fixture setup.

The wider `domain/iva` suite plus the import-hygiene and docstring-link gates ran
409 passed and 5 failed; every failing path named belongs to another lane
(`_classifier_inputs`, `_foreign_asset_redeclaration`, `_m720_redeclaration_gate`,
`_ledger_evidence_batch_payloads`, and seven peer test modules reaching private
imports). None is this module. `ruff check`, `ruff format --check` and `ty check`
are clean on both files.

## The first mutation attempt was fully green, and that was the finding

Both mutations initially returned 31 passed. The patch was installed in a
session-scoped autouse fixture, which runs at the first test's setup -- after the
gate module has already executed its `from .. import ...` and bound the original
function objects. Rebinding the facade attribute afterwards reached nothing.

The probe still printed a convincing delta, because it called the wrapper
directly. It validated the detector while never validating the target, which is
the failure that passes forever regardless of what the gate is aimed at. The fix
was to patch at plugin module scope, before test modules are collected, and to add
a `pytest_collection_finish` check asserting the gate module's OWN attribute is
the wrapper -- interrogating the binding under test rather than the one just
written. Both mutations bit immediately afterwards.
