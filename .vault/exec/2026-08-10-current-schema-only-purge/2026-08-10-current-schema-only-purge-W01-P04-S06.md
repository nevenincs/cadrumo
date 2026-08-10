---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:037c4154f244e6e262039078314742674a500493cf337acee87484056af07990'
step_id: 'S06'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Delete mapping-without-invoices coercion from InvoiceCatalogue validation

## Scope

- `src/cadrumo/domain/invoices/_models.py`

## Description

- Refuse a non-empty mapping that does not carry the canonical entries key,
  where the validator previously wrapped it and returned a valid catalogue.
- Route the refusal through the module's existing typed error, naming the key
  expected and the size of the bare mapping received.
- Preserve the identity arm, the canonical-payload arm and the whole iterable
  construction arm including its duplicate-identifier refusal.

## Outcome

Landed in `7afcc4b` with its proof step; the six consumer call sites it broke
were absorbed in `e12d8c0`.

The deleted arm took an arbitrary mapping and promoted it into a catalogue whose
keys no writer had established to be invoice identifiers. The resulting record is
indistinguishable afterwards from one written correctly, which is what makes a
silent wrap worse than a refusal.

The refusal is conditioned on the mapping being NON-EMPTY. An empty mapping is
not a serialized payload missing its wrapper; it is the field keyword arguments
of a catalogue constructed with no entries, and it is still accepted
deliberately. Two call sites in the tree rely on that and were confirmed and
left untouched.

## Notes

The same accept-a-bare-mapping-or-an-iterable validator exists in two further
catalogue models, for attachments and for transactions. Only the invoices copy is
in this row's scope and only it was changed. A semantic sweep confirmed all three
are the same concept carrying the same tolerance: the attachments copy has zero
bare-mapping callers and would be near-free to remove, while the transactions
copy has eleven or more call sites and needs scoping before it is opened. Both
are recorded for a decision rather than left as an undocumented asymmetry.
