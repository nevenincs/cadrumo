---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:3af7e704cea1cb20103aa6d60c9993f3c4a12fa4dfb9ebc1ec09e8d840357ed2'
step_id: 'S15'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# declare `AeatCsv` in `core/identity/` at the shape decided in `W02.P03.S13`

## Scope

- `src/cadrumo/core/identity/__init__.py`

## Description

This row was DELIVERED BEFORE THIS RECORD EXISTED. The record is reconstructed
from the history rather than written alongside the change, so what follows is
what the commits actually did, verified against the tree at reconstruction time.

Two commits carried it, three days before this record.

`c272504f9d` declared the alias. It enrolled the whole AEAT-issued identifier
namespace family at once - expediente id, clave de liquidacion, presentation id
and the CSV - so the CSV declaration arrived as one member of a batch rather
than as a row-shaped change. The alias is an annotated `str` carrying a
before-validator that normalises through the shared comparison form, then string
constraints pinning minimum length, maximum length and an anchored uppercase
alphanumeric pattern, every bound read from the canonical shape module rather
than restated as a literal.

`78b8023a1c` exported it from the package facade, adding the import and the
`__all__` entry. The row named the facade file as its scope, so the row is not
satisfied by the declaration alone; the export commit is the half that closes it.

## Outcome

Delivered, and the delivery matches the row. The alias resolves from the
package facade, and its bound is the 8-32 uppercase-alphanumeric contract the
canonical shape module owns, read from that module's constants rather than
re-spelled - so the shape decided upstream and the shape enforced at the model
boundary are one declaration, not two that agree today.

One divergence from the row's letter, recorded rather than smoothed over: the
row reads as a single declaration step and the delivery took two commits, with
the alias declared but unexported in between. Nothing consumed it in that
window, so the gap had no effect, but a reader diffing the row against a single
commit will not find the whole row in either one.

The alias normalises BEFORE its constraints run rather than after. That ordering
is load-bearing and the declaration's own docstring records why: a trailing
uppercase transform would run after the pattern check and would therefore still
refuse the lowercase value it was added to accept. Normalising first means the
constraints only ever see the canonical form.

## Notes

The declaration site has been edited since by `f6b7ccb518`, which removed a
different, dormant member of the same namespace family. That commit belongs to
another row and did not touch the CSV alias.

The bound is the one place in this alias family where the TIGHTER of two
competing declarations won. The reasoning is carried in the declaration's own
docstring rather than left to be inferred, because the sample behind it is three
real captures rather than a published specification - what makes the tighter
bound safe is the margin on both sides and the asymmetry of the two failure
directions, not the size of the sample.
