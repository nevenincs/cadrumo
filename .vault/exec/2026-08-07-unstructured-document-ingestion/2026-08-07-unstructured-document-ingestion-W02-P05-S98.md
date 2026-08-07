---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a9075f4d4cd990d9307f2fa5b3861715ec7c03c1ffd723564030c7aab1e4551c'
step_id: 'S98'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Status: the row is deliberately left unchecked

Four of the five things the row asks for have landed and are verified. The fifth,
a grounded parity test reproducing a worked example from an official source, has
not been done, and the row stays open until it is. The blocker and the shape of
the remaining work are named at the end rather than left implicit.

## What changed

The classification decision table decided WHERE an operation is located and
carried none of the law behind it. The predicates held the conditions in Python
and the provision establishing each placement existed nowhere at all -- not in a
comment, not in the per-category catalogue beside it. A predicate is logic and
stays in Python; the provision behind it is regulatory content, versioned by
filing year, and now lives in the registry at
`registry/aeat/iva/place_of_supply/2025.toml`.

Keyed by rule rather than by category, because the fork the table exists for is
finer than a category. Three separate reverse-charge rules all resolve to
`DOMESTIC_REVERSE_CHARGE` while resting on different provisions, so a
per-category table cannot say what establishes any one of them.

## The fork is the point, and it is the statute's own

LIVA art. 68 is titled *Lugar de realización de las entregas de bienes*; art. 69
is *Lugar de realización de las prestaciones de servicios. Reglas generales* and
art. 70 the *Reglas especiales*. That is the goods/services fork stated by the
law itself, and it is why supply nature has to be established before origin and
destination mean anything on a cross-border branch.

Both headings are asserted verbatim against the bundled consolidated text inside
the gate, so the pairing of nature to placement article is checked against the
statute rather than against a literal typed beside the row.

## An absent nature is a finding, not a blank

A rule whose provisions do not fix whether goods or services were supplied omits
`supply_nature`. The omission means the cited articles are silent; it never means
the row is unfinished. Carrying the row with the field absent, rather than
omitting the row, is what lets a reader tell those two apart.

The worked case is the Union scheme. LIVA art. 163 unvicies reaches "presten
servicios" and "ventas a distancia intracomunitarias de bienes" alike, so citing
it alone determines nothing. The two goods rules that ride it fix the nature on
art. 68 and the services rule on art. 69, and a dedicated case asserts that no
rule ever takes its nature from that article -- with a guard refusing to pass
vacuously if no rule cites it at all.

The domestic rules omit it for a different reason: both placement rules put a
domestic operation in the same territory, so its treatment turns on the rate
tier. Demanding the distinction there would refuse invoices for a fact their own
treatment ignores. That is the laziness property expressed as data rather than as
a comment, and it is mutation-proven below.

## The sentinel, and why it is exempt rather than absent

`R99_fallthrough` is emitted when no rule matches. It names an application-level
"could not classify" state, not a tax treatment, so it has no article to codify
and demanding one would manufacture the appearance of a legal basis it has none
of by design. It carries a row marked `legal_basis_exempt`, mirroring the same
distinction the sibling regulation table already draws, and the model refuses an
exempt row that cites anything or fixes a nature -- so the exemption cannot become
a place to park a half-filled row.

Finding it was the parity gate's doing. It is not a member of the decision table,
so an initial parity check against the table alone would have left the one rule id
a reader is most likely to meet on an unclassifiable document outside the
grounding contract entirely. The denominator is now every rule id a RESULT can
carry.

## Verification

Gate: 12 passed. Wider `domain/iva`: 405 passed, 0 failed. Sequential, cache
provider disabled, marker `unit`. `ruff check`, `ruff format` and `ty check`
clean. Landed at `4b9a0e2c00`, four files, 619 insertions and zero deletions.

Every one of the twelve cited provisions was confirmed to resolve to a real legal
catalogue entry before a row cited it, and the gate re-checks that from the data.

Two mutations, both from outside the repository, both installed at plugin module
scope with a `pytest_collection_finish` check asserting the gate module's own
attribute is the wrapper. Defaulting a silent rule's nature to goods returned 5
failed and 7 passed, reddening every domestic laziness case. Flipping one
services rule to claim goods while it reads only arts. 69 and 70 returned 1 failed
and 11 passed, reddening precisely the statute check and nothing else.

The parity gate bit twice during development, which is the evidence it is not
decorative: it caught a rule id guessed from a function name
(`R15_distance_sales_b2c`, not `..._outbound`) and it caught the ungrounded
fall-through.

## What is not done, and what it needs

The row also asks for a grounded parity test reproducing a worked example from an
official source. It is not written.

The obstacle is that no such worked example is available in a form that can be
read without a substantial separate effort: the bundled IVA corpus for each year
is a `source.pdf` plus a structure directory, and the existing manual oracles
under `corpus/manual_oracles/` are all Modelo 100, none covering an
intra-community operation. Authoring an oracle from anything other than an
official worked example is what the grounding rules forbid, and an oracle asserting
a figure this code produces would be tautological besides.

The work it needs is its own Step: locate a localisation worked example in the
Manual práctico IVA, extract the figures with their raw-evidence locator, bundle
it as a manual oracle keyed by expected values, and assert the engine reproduces
it independently. That should not be folded into this row silently, and the row
stays unchecked until it is done or explicitly deferred with a reference.

The mapping is also not yet consumed. `IvaInvoiceClassificationCriteria` still has
no production caller; another Step owns the assembly that will call it. This Step
supplies the branch selector and its grounding, and stops there.
