---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:81cd200c34a6f0651862bfd9a0072f590dbfd82efbf2c2a803d683e1b094a63f'
step_id: 'S11'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Replace the hardcoded ceiling literals in the two descendant test modules with reads of the registry parameters the campaign authored, matching how the new eligibility module already resolves them, because inlined regulatory figures decouple those tests from the authority and would keep them passing against a stale ceiling if a future revision moved it

## Scope

- `src/cadrumo/domain/contribuyente/tests/test_custodia_compartida.py`
- `src/cadrumo/domain/contribuyente/tests/test_descendant_info.py`

## Description

## Outcome

Partially landed, and the Step stays open until the remainder commits. Recording the split
rather than claiming completion, because half the work sits uncommitted in the working tree.

The whole agent fleet hit capacity limits mid-phase, so the coordinator executed this Step
directly.

What the investigation changed about the fix. The audit that raised this finding proposed
reading the registry parameters, and that is what shipped, but the reasoning needed
correcting on the way. Neither module ASSERTS the ceiling values, and no case data touches
the rentas or own-return fields at all: the thresholds are required by the signature and
otherwise inert. That makes the fix low-value rather than wrong. The audit's underlying
point stands and is the reason to do it anyway -- a revision moving a ceiling should not
leave these modules silently assuming a stale figure.

A layering question was raised and resolved. A first reading found a sibling test in this
package reaching the registry and treated it as precedent, which was wrong: that test reads
a bundled data file, not the registry authority. The real precedent is in a sibling domain
package, whose tests reach the authority through core. Core is the base layer, so a domain
test may depend on it and the pattern is legitimate.

The helper landed as a single support module in this test package rather than as a copy in
each consumer. Two copies would have been a third and fourth variant of a lookup that
already exists in the application-layer eligibility module, which is the fragmentation the
operator's canonical-home directive exists to prevent.

That decision was immediately validated by something outside this Step. A peer working the
same file concurrently EXTENDED the new support module with birth-order and under-three
resolvers rather than adding a second lookup of their own, and used it to retire the tranche
literals as well -- a larger instance of the same breach that the originating audit did not
flag. Both modules now carry zero regulatory literals.

The concurrent edit was briefly observable as a broken file: the peer's call sites landed
before their import did. That was live peer work mid-edit, so it was left alone rather than
repaired, and it resolved on its own. The coordinator committed only its own two coherent
files under an explicit pathspec, verified the staged set carried nothing foreign, and
confirmed the landed file set after the fact.

Gates: the custodia module passes at 8 and the descendant module at 44, both sequentially.
Lint and format clean on the committed files.

Outstanding before this Step closes: the peer's half is complete in the working tree but
uncommitted, touching the support module, both consuming modules and a third grounded
module. The Step's objective is met in the tree and half of it is in history.

Closed. The peer half landed and both modules now read every Art. 58 figure and both
ceilings from the registry, verified by grep: zero regulatory literals remain in either.

The collision resolved the way the canonical-home directive intends. Two agents reached the
same Step from opposite ends within the same minutes, one landing a support module and the
other mid-edit with a script whose import replacement missed because the line had already
changed. The second agent repaired by hand ON THE FIRST AGENT'S NAMING, extended that module
with the tranche readers rather than shipping its own, and deleted its duplicate. Two
parallel lookups were within one edit of existing and neither shipped.

The two ceilings also joined the minimo grounding gate, which is where a euro literal
legitimately belongs because there the figure is the assertion target rather than an inert
parameter.

One finding surfaced in passing and was acted on: an engine scenario declared no marital
signals, so it exercised the unpartnered branch by omission while reading as an ordinary
family. It now names the household it models. That is the semantic drift a grounding pass
warned about -- figures unchanged and nothing red, but a test proving something other than
what its name implies.

## Notes
