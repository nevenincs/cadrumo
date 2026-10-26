---
tags:
  - '#reference'
  - '#facturae-invoice-class'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:58cd6df951f8e998e6411fcacb9b13f866ec97346391297e544561277b32dc87'
related: []
---

# `facturae-invoice-class` reference: `the code set is six values on two axes, and it is not the regulatory taxonomy`

## Summary

The structured e-invoice reader deliberately does not read Facturae's
`InvoiceClass` element. The reason recorded at the time was that the code set is
a closed regulatory vocabulary the repository does not bundle, and writing it
from memory would be inventing one. That reason has now been removed: the code
set is bundled, extracted from the schema the tree already trusts.

### The artefact is the one already in the tree, byte for byte

The country-code bundle under `src/cadrumo/_data/corpus/facturae/` records its
provenance as `CountryType` extracted from Facturae 3.2.2 at a stated URL, with
a `source_sha256` and a byte count. Re-fetching that URL returns **190062 bytes
hashing to `b4bbcd587f5fb0a8a906336cca09b0a40d06ffaa78c6a62f6e438c4e6ea86e07`**,
identical to what that bundle records. `InvoiceClassType` lives in the same
document, so extracting it needs no trust the tree has not already extended.

The extraction is committed as `facturae-3-2-2-invoice-class.json`, in the same
shape as its sibling and carrying the same provenance block.

### Six values, not five -- and the miss is instructive

The deferral note named the vocabulary as `OO` / `OR` / `OC` / `CO` / `CR`. The
schema carries **six**:

| code | es | en |
|---|---|---|
| `OO` | Original. | Original Invoice. |
| `OR` | Original rectificativa | Corrective. |
| `OC` | Original recapitulativa. | Summary. |
| `CO` | Copia original. | Copy of the Original. |
| `CR` | Copia rectificativa. | Copy of the Corrective. |
| `CC` | Copia recapitulativa. | Copy of the Summary. |

`CC` was missing from the remembered list. That is the whole argument for the
refusal to write it from memory, made concrete: a five-value set would have
parsed real documents and silently rejected or misread every copy of a summary
invoice.

### The codes carry TWO axes, and the domain enum carries neither of them

The first character is original versus copy; the second is
ordinaria / rectificativa / recapitulativa. So the set is a 2x3 product, not a
flat list.

The domain's own `InvoiceClass` is a different vocabulary answering a different
question: `ORDINARIA`, `SIMPLIFICADA`, `RECTIFICATIVA`, closed by RD 1619/2012
art. 6.1.a. The two overlap on one word and agree nowhere else:

- **`SIMPLIFICADA` has no Facturae counterpart.** It is a Spanish regulatory
  class, not a document-type code.
- **`recapitulativa` has no domain counterpart.** A factura recapitulativa is
  RD 1619/2012 art. 13, a real class this codebase does not model. Mapping `OC`
  onto `ORDINARIA` would discard that fact silently.
- **The copy axis has no home at all.** A copy is not a newly issued invoice,
  and nothing in the domain records the distinction.

A mapping function from one to the other would therefore be lossy in two
directions at once, which is why bundling the vocabulary is a separate act from
consuming it.

### What consuming it would improve

`_evidence_draft.py` currently derives `RECTIFICATIVA` by inference: an
`ORDINARIA` draft that resolved a corrective reference is reclassified. That is
sound and grounded, but it is a derivation from the PRESENCE of a field rather
than from a declaration. A document stating `OR` declares its class outright, so
the declared code could ground the classification and the existing inference
could stay as the fallback for documents that declare nothing.

That change touches the parser, the draft assembly and the domain vocabulary at
once, and it is not attempted here.
