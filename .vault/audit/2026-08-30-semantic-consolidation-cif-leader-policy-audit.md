---
tags:
  - '#audit'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:e308ba54e671c646018004ec99f42fe920062143196710af23aaa1dea8fc5df7'
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

## The divergence is on a live path, not just in the module pair

Found while attempting an unrelated consolidation, and it raises the severity.

The apoderamiento flow validates the represented party's NIF through
:func:`validate_identity` -- `application/auth/apoderado_flow.py:102`, which the
module docstring names as the canonical authority for that field.
:func:`validate_identity` is the ``_documents`` implementation, so it applies the
DIGIT-ONLY policy.

The canonical pydantic alias for the same concept, :data:`SubjectTaxId` in
`core/identity/__init__.py:213`, runs :func:`validate_spanish_tax_id` -- the
``_tax_id`` implementation, which applies the MIXED policy.

    validate_identity("A1234567D")        -> IdentityError   (refused)
    validate_spanish_tax_id("A1234567D")  -> "A1234567D"     (accepted)

So the two policies are not merely co-resident in one package. One is reached by
the interactive flow and the other by the field type any model would adopt for
the same value. An operator entering an ABEH-leader CIF with a letter control
is refused by the wizard; the same value validates if it arrives by any path
that types the field instead.

This also blocks an otherwise routine consolidation. ``represented_nif`` carries
``min_length=1, max_length=16`` at three CLI sites and a fourth in
``apoderado_service``, and the obvious fix is to adopt :data:`SubjectTaxId`.
Doing so would move that field from the flow's policy to the opposite one
without anyone deciding to. The length bound was consolidated instead, and the
checksum policy left exactly where it is, pending the ruling below.

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

## Resolution

The operator ruled on 2026-08-31: no two validators, merge them. The ruling
settles the question this audit left open, and the direction was not a
free choice -- AEAT partitions the CIF kind letters three ways, `_documents`
already implemented that partition, and `_tax_id`'s own module docstring stated
it correctly while the code beneath it accepted the letter form for `ABEH`. The
laxer surface was wrong against the authority AND against its own documentation,
so the merge target was determined rather than picked.

What landed:

- `_documents._validate_cif` is the sole CIF leader policy. Its control-character
  class check moved out of the shape regex, so the three-way partition decides
  which control forms are legal rather than a character class deciding it in
  advance.
- `_tax_id`'s four restated validators -- NIF, prefixed NIF, NIE, CIF -- are
  gone, 140 lines. `validate_spanish_tax_id` now normalises, width-checks,
  refuses an unrecognised leader, then delegates to `validate_identity`. The
  return SHAPE is all that differs between the two surfaces, which is what the
  module docstring always claimed.
- The refusal divergence this audit flagged is resolved in the richer direction:
  the plain-English message the deleted surface carried is now on every raise in
  `_documents`, so `str(exc)` is a sentence again rather than a translation key.
  Collapsing to the poorer payload would have degraded every consumer that logs
  the exception.
- `_compute_cif_check`, orphaned by the merge, is deleted.

Behaviour change, deliberate: an `ABEH` CIF with a letter control is now
REFUSED. `B1234567D` was accepted before and is not a valid CIF. One test
asserted that acceptance as the contract -- named
`test_validate_spanish_tax_id_accepts_abeh_letter_form`, with a docstring
explaining the historical dual form -- and was corrected rather than worked
around. No fixture or registry value in the tree carries an `ABEH` letter-control
CIF, so the blast radius was that single assertion.

Two diagnostics sharpened as a consequence, both re-pinned with their reason:
`W1234567L` now names the check letter AEAT expects instead of reporting a shape
miss, and `A12345670` reports a wrong check DIGIT rather than the mixed-kind key
it inherited from the laxer copy.

### The gate

`core/identity/tests/test_single_identity_algorithm.py` keeps it merged. It is
structural, not a behavioural sample, because a sample cannot see a validator no
test calls yet: each policy table and the checksum arithmetic must be declared
once, outside prose, in the pinned authority. A third assertion refuses to let a
rename hollow the authority out and leave the first two vacuously true.

Proved by mutation from outside the repo -- a probe module restating `"ABEH"`
reds the first arm, one recomputing `% 23` reds the second, and replacing the
authority's own table with an equivalent expression reds the anti-vacuity arm.
