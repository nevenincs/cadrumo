---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:053042f5e5e65239f1c667cdf86b9d5d9c52a8f147a694896348f0ec97a0ee1f'
step_id: 'S24'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# DONE. The silent misclassification is closed end to end. The Facturae reader walked past Corrective/InvoiceNumber deliberately - its own comment said a rectificativa restates the corrected number there - while the confirm defaulted the class to ORDINARIA regardless, so the fact was seen and discarded and the Invoice model's rectificativa invariants never fired because nothing ever stated the class. Now read, carried on the draft, layered under the operator at confirm, and exposed as --invoice-class, --rectifies and --series for documents that state none of their own. GROUNDING LANDED: RD 1619/2012 art. 15 has a legal-catalogue entry quoted verbatim from the bundled consolidated text at the a15 anchor, attributed reviewed_by agent-review, which the shipped catalogue already establishes as practice - the earlier claim that this surface was operator-gated was WRONG, inferred from convention rather than read from the schema. THE CLASS IS DERIVED from the corrected reference because the model ties the two in both directions. Facturae's own InvoiceClass code element is deliberately NOT read: a closed regulatory vocabulary this repo does not bundle, and mapping its tokens from memory would be inventing one. Stating the class exposed three latent gaps, all closed - the document's own series was never layered, the new draft field had to reach the extract payload which the loss-forbidden waist gate caught, and the override channel needed --series because art. 6.1.a.2 obliges a rectificativa into its own. Omission is load-bearing: the runner omits the class argument rather than sending the service default, or every confirm would overwrite a recovered rectificativa

## Scope

- `src/cadrumo/application/ledger`
- `src/cadrumo/entrypoints/cli`

## Description

- Ground the class axis in the bundled corpus and land its legal-catalogue
  entry.
- Read the corrected invoice number the parser was stepping over.
- Carry it to the draft, layer it under the operator at confirm, and derive the
  class from it.
- Expose the override for documents that state no class of their own.

## Outcome

Delivered end to end, and the defect was exactly what the row called it: a
SILENT MISCLASSIFICATION rather than a missing feature.

The Facturae reader already walked past `Corrective/InvoiceNumber`. Its own
comment said a rectificativa restates the corrected invoice's number there, and
the direct-child scoping stepped over it deliberately, to read the invoice's own
number rather than the one it corrects. That scoping is right and stays. What
was missing is that nobody then read the corrected number at all.

Meanwhile the confirm defaulted the class to ORDINARIA regardless. So the fact
was on the document, was seen, and was thrown away -- and because nothing ever
STATED the class, the `Invoice` model's rectificativa invariants never fired to
object. An invoice correcting another reached the catalogue indistinguishable
from one that corrected nothing.

THE CLASS IS DERIVED from the corrected reference rather than carried beside it.
The model already ties the two in both directions, so a class field and a
reference field that could disagree would be two spellings of one fact with no
authority between them.

FACTURAE'S OWN `InvoiceClass` ELEMENT IS DELIBERATELY NOT READ. The bundled
fixture carries `OR`, and that vocabulary -- original, rectificativa, and their
copies -- is a closed regulatory code set this repository does not bundle and no
registry entry defines. Mapping those tokens from memory would be inventing a
regulatory code set, which is the one thing the grounding rule forbids outright.
The `Corrective` block carries the same fact and the parser's own docstring
already states its meaning, so the reading rests there.

STATING THE CLASS EXPOSED THREE LATENT GAPS, all closed here. The document's own
SERIES was never layered either, and the model refuses a rectificativa without
one -- correctly, and it could not refuse before, because nothing told it the
class. The new draft field had to reach the extract payload, which the
loss-forbidden waist gate caught within one run. And the operator override was
incomplete without `--series`: someone able to declare the class but not the
series can only declare an invalid invoice.

OMISSION IS LOAD-BEARING at the CLI. The confirm service defaults the class to
ORDINARIA, so passing that default through whenever the operator said nothing
would override a rectificativa the reader correctly recovered -- reinstating the
silent misclassification on every confirm. The runner omits the argument instead
of sending a default, and a case holds that.

## Notes

THE ROW'S BLOCKER WAS MY OWN ERROR, and it cost this step a session. I recorded
that the legal-catalogue half was operator-gated because `review_status` on a
legal reference is `Literal["reviewed"]`, and concluded that authoring an entry
is by construction asserting a completed human review. The first half is true.
The conclusion is not: `reviewed_by` is `str = Field(min_length=1)`, and
`reviewed_by = "agent-review"` is already shipped in the very file I was
reading. Agent-authored entries with honest attribution are established practice
here.

So I inferred a constraint from convention and reported it as a schema fact,
which is precisely the error class this campaign keeps finding in rows written
by others. It took the operator pushing back for me to check the field I had
never read. The governing rule bars stamping an agent entry under the OPERATOR'S
name without the cross-check -- not authoring one, attributed honestly, after
doing the cross-check.

The grounding cross-check was done against the bundled consolidated text at the
`#a15` anchor rather than a secondary source, and the `required_text` phrases
are quoted from it.

A test of mine asserted on the refusal's PROSE and had to be corrected to assert
on the envelope's structure instead. The suite it sits in states the rule in its
own header: assertions are on codes, severities and structure, never on prose,
which is localised.
