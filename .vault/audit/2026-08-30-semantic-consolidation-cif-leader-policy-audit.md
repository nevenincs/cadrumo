---
tags:
  - '#audit'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:9b6099701484831705696121976fa03f7aa18a533f9cf8a22772632d55330256'
related: []
---

# `semantic-consolidation` audit: two CIF validators, opposite answers

## The finding

`cadrumo.core.identity` validates a CIF check character twice, over the same
`_cif_check_value` arithmetic, under **opposite acceptance policies** for the
`ABEH` leader class:

- `core/identity/_tax_id.py:240` `_validate_cif` treats `ABEH` as MIXED --
  a digit or a letter control is accepted.
- `core/identity/_documents.py:225` `_validate_cif` treats `ABEH` as
  DIGIT-ONLY -- a letter control is refused.

Both carry an `ALT-CIF-LEADER-RATIONALE-*` comment describing the divergence as
deliberate, and `_cif_check_value`'s own docstring says the kernel "leaves the
digit-vs-letter rendering and the per-kind acceptance policy to the caller".
Neither comment cites a source for which policy is right.

## Why this is a defect and not a design choice

`_tax_id.py`'s own module docstring, at lines 127 to 131, states the rule:

> Leading letters in ``PQRSNW`` require a **letter** control drawn from
> ``JABCDEFGHI``; leading letters in ``ABEH`` require a **digit** control; all
> other leaders accept either form.

The module documents digit-only for `ABEH` and implements mixed. A comment
elsewhere in the same file calls that divergence deliberate, but the two
statements cannot both be true, and nothing reconciles them.

## Reproduction

`A1234567D` -- an `A` leader whose check value 4 renders as the letter `D`:

    validate_spanish_tax_id("A1234567D")   -> "A1234567D"   (accepted)
    _documents._validate_cif("A1234567D")  -> IdentityError  (refused)

One package, one input, two answers. If the digit-only reading is correct then
`validate_spanish_tax_id` -- the function every operator-facing surface calls --
accepts identifiers AEAT rejects.

## What is NOT established

Which policy is AEAT-correct. The governing norm for the composition of the
NIF of a legal person is not in the bundled corpus under
`src/cadrumo/_data/corpus/normatives/html/`, and this campaign does not invent
tax semantics. No test pins either policy: a search of
`core/identity/tests/` for an `ABEH`-leader case returns nothing, so the
divergence is unpinned in both directions.

Because the behaviour is filing-grade identity validation, the fix is a tax
review against BOE or AEAT text and an ADR ruling, not a code judgement made
from the shape of the duplication. **No behaviour was changed.**

## Recommendation

1. Ground the leader-class policy against the official norm and bundle the text.
2. Rule which validator is authoritative in an ADR.
3. Collapse to one procedure, so the arithmetic and the acceptance policy live
   together rather than the kernel deferring policy to two callers who disagree.
4. Pin the ruling with a test per leader class, including the `ABEH` case that
   is currently unpinned.

## Secondary finding: the NIF/NIE procedure beside it

The same two modules each implement `_validate_nif`, `_validate_prefixed_nif`
and `_validate_nie` over the shared `nif_check_letter` table. A triage sweep
nominated these as substitutable duplication. Checked:

- The ACCEPTED SETS are identical. `_tax_id` gates shape with slicing plus
  `isdigit()`/`isalpha()` while `_documents` uses `^(\d{8})([A-Z])$`, so the
  former's gate admits a non-ASCII letter the latter's does not -- but the
  checksum comparison that follows rejects it either way, because
  `nif_check_letter` only ever returns ASCII. Probed rather than reasoned:
  `12345678Z` accepts on both, `12345678Ñ` refuses on both.
- The REFUSALS are NOT identical. `_tax_id` raises with a developer-facing
  f-string as well as the translated key; `_documents` raises with the
  translated key alone. Extracting one shared compare-and-raise therefore
  changes one side's error payload, and which payload survives is a decision,
  not a mechanical move.

So the substitutability verdict is: substitutable on behaviour, divergent on
refusal. Worth collapsing alongside the CIF ruling above, since both live in the
same pair of modules and the CIF question already forces a decision about which
of the two surfaces is authoritative. Not collapsed here.

## Provenance

Nominated by a duplication-triage sweep, then confirmed here against current
code: both implementations read in full, the contradiction with the module
docstring located, and the divergence demonstrated by execution rather than
inferred from the source.
