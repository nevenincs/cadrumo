---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:12599f18bf892171cb92d233c6fce7113ad6bcfa77a057e17c5515d1b392a1e5'
step_id: 'S172'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Decide whether a Spanish VAT identification can be established from evidence

## Scope

- `src/cadrumo/domain/iva`

## Description

- Measure what a Spanish intra-community identifier resolves to today, through the production path rather than by reading the vocabulary.
- Establish why the exclusion exists, separating the implementation reason from the reason the module states.
- Determine whether closing it would be safe for the establishment axis.
- Record the decision, and correct the module prose that presented an open question as a settled refusal.

## Outcome

**The decision is that the identification axis SHOULD be establishable on both sides.** The current one-sidedness is an implementation boundary that the module described as something stronger, and nothing legal or evidential supports leaving it closed.

Three measurements carry it.

The axis is genuinely one-sided today. `ES` is absent from the NIF-IVA prefix vocabulary, there is no Spanish format spec, and a Spanish intra-community identifier resolves to no country and no identification -- while a German one resolves to both. So an intra-community sale has the counterparty's identification established from the paper and the filer's own only assertable, on the one axis where the paper states it.

The reason is narrower than the module said, and it is structural rather than legal. This path recognises a prefix by matching the number's body against the pattern its own prefix claims, and Spanish identifiers are validated by the AEAT control-letter checksum instead of by a structural pattern. So `ES` could not have joined the vocabulary the way its siblings did. That is a real constraint and it is not a decision that the evidence does not exist.

Closing it would be safe for the establishment axis by construction rather than by care. The establishment side composes through the country resolver, which returns nothing for Spain by design because a country code cannot separate the three Spanish territories. So a Spanish prefix admitted to the identification vocabulary cannot leak a Spanish establishment: the identification would resolve and the territory would still be refused, which is exactly the split the fifth amendment made.

The capability already ships. The AEAT control-letter validator is in the tree and is what a Spanish format spec would delegate to, so closing this is a wiring question rather than new authority.

**What was NOT done here, and why.** Implementing the decision lands in `core/identity` -- the prefix vocabulary and a checksum-capable format spec -- which is outside this row's stated scope. It also wants the format grounded against a provision the way every other regulatory value in the tree is, and this session did not establish that grounding. So the implementing change is a separate row and is named as one rather than smuggled in under a decision row.

What WAS done in scope is the prose: the module said a Spanish identification is never inferred from a prefix that is never printed. The clause about printing is unsupported by anything in this tree, and it turned an open scope question into a settled refusal for every later reader. It now says the absence is an implementation boundary and that whether `ES` should join is open.

## Verification

Measured through the production functions rather than by reading the vocabulary:

    ES in NifIvaPrefix: False
    ES format spec: None
    ESB12345674  -> country=None  identification=None
    B12345674    -> country=None  identification=None
    DE811234567  -> country=DE    identification=de

The 27 prefixes present are every Member State except Spain, plus Northern Ireland.

The capability that would close it, confirmed present:

    validate_spanish_tax_id  (AEAT control-letter table)

Domain lane after the prose correction:

    uv run --no-sync pytest src/cadrumo/domain/iva/tests -n0 -q -m unit
    690 passed in 40.80s

## Notes

The claim that a Spanish intra-community identifier is printed in an `ES`-prefixed form is stated in this record as the reason the question is open, and it is deliberately NOT asserted in the module or encoded anywhere. The bundled corpus carries the intra-community operator concept but this session did not locate a provision fixing the identifier's printed form, so the implementing row must ground that against a provision rather than inherit it from here. Correcting prose to stop asserting an unsupported negative does not require asserting the positive.
