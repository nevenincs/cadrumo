---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:43261fc5e8a8df78d88a21ea440e5724b5c01bdb5f0f9649d82d60b086e1bb9f'
related:
  - "[[2026-08-14-registry-campaign-sequencing-audit]]"
---

# `registry-campaign-sequencing` audit: `A filing-load-bearing type mapping lives only in application code`

## Scope

One finding, routed rather than fixed, plus the reason its obvious remedy is
worse than the defect. Detail-record row fields are emitted into filing artefacts
with a scalar type that no registry declaration supplies. The mapping from row
field to type exists in exactly one place, a hand-maintained dictionary in the
filing application layer, and thirty registry bindings fall outside it.

An immediate safety change has landed separately: an unmapped row field now
refuses instead of defaulting. This records the convergent repair, which is
authoring work across five modelo trees and belongs to their owners.

## Findings

### row-field-type-has-no-registry-home | high | A fact that decides filed bytes is declared only in application code

`_ROW_FIELD_DATA_TYPES` in the filing package maps fourteen row-field names to a
scalar type. It is the sole authority for that fact anywhere in the tree.

The registry does type row fields, but on a different axis. Each detail-record
family declares a closed vocabulary of legal field NAMES -- related-party,
foreign-asset and atribucion selectors each carry their own `Literal` -- and
registry validation enforces membership. What no registry declaration states is
what scalar type any of those names carries. The runtime classifier that maps a
declared `data_type` to a value family is reachable and correct; it simply has
nothing to classify, because the binding never declares one.

So a value's type on a filed artefact is decided by a Python dictionary, versioned
with the application rather than with the filing year, and invisible to every
registry gate.

### deleting-the-hand-list-is-worse-than-keeping-it | high | The obvious convergence remedy would break the cases that currently work

A hand-list where a registry declaration belongs reads as an obvious candidate for
deletion, and the reasoning is worth recording because it does not survive
contact with the data.

Thirty-five bindings carry a row field the list maps correctly. Thirty carry one
it does not, and those currently fall through to a decimal default. Deleting the
list without first declaring the types in the registry would send all sixty-five
to the default, converting thirty-five correct emissions into wrong ones to fix
thirty already wrong. The finding is right about the smell and wrong about the
remedy.

A separate figure makes the same point from the other side. Eight hundred and
twenty-nine bindings declare neither a `data_type` nor a row field; these are
ordinary scalar money bindings for which the decimal default is correct. Any
change that makes the default refuse outright, rather than refusing only for an
unmapped row field, would break every one of them.

### fourteen-text-values-emit-as-decimal | high | Names, tax ids and a date are typed as money on a filing path

Of the thirty unmapped bindings, fourteen read unambiguously as text and are
spread across five modelos:

- modelo 184 -- `member_tax_id`, `member_legal_name`
- modelo 190 -- `perceptor_tax_id`, `perceptor_legal_name`
- modelo 193 -- `perceptor_tax_id`, `perceptor_legal_name`
- modelo 232 -- `counterparty_tax_id`, `counterparty_legal_name`,
  `operation_kind_code`, `transfer_pricing_method_code`
- modelo 360 -- `supplier_tax_id`, `member_state_code`, `operation_kind_code`,
  `operation_date`

The path is the draft builder's binding-value assembly, on the branches handling
row-shaped inputs, which is where detail-record rows arrive. It is not test-only.

The exposure is latent only because no modelo can emit a byte while the filing
gate refuses. It differs from the other latent finding recorded in this campaign
in an important way: nothing is missing between the caller and this code. It
lands the moment attestation clears, rather than waiting on a surface nobody has
built.

## Recommendations

Each row-field binding should declare its own `data_type` in registry TOML. The
filing path already prefers a declared type over the hand-list, so every binding
that gains one leaves the list behind with no application change, and the list can
be deleted once the last one is declared. That ordering matters: the list must go
last, not first.

This is thirty-plus authoring changes across the modelo 184, 190, 193, 232 and 360
trees, and it is a claim about what each field holds, so it belongs with whoever
owns those trees rather than with the filing package.

Until then the safety change stands: a row field the list does not map refuses,
naming the binding, instead of emitting a name or a tax id as a decimal. The
refusal adds red to modelos that already cannot file and removes a silent wrong
answer that would otherwise land the day the filing gate clears, which is the
trade at its most favourable.

A follow-on decision record, if one is opened, must rule on whether the scalar
default survives at all once row fields declare their own types, or whether every
binding should be required to declare one and the default removed entirely.
