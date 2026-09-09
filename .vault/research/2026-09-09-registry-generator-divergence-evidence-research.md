---
tags:
  - '#research'
  - '#registry-generator'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:868e6e78618c5dc0777962adb7f5cbdcbad29e174e028f5288014b6315772f36'
related: []
---

# `registry-generator` research: divergence evidence

## Why this document exists

A failing test led to one wrong field. This document records what a systematic measurement found
instead: a class of divergence between what the official designs state and what the registry
ships, its size, its cause, and — importantly — which parts of it are dangerous and which are not.

The headline is not the count. It is the mechanism: **the generator derives faithfully from the
columns it reads, and substitutes a constant for every column it does not.**

## How the measurement was made

No new instrument was needed. Every generated revision already ships a provenance manifest whose
`field_derivations` list is the serialized output of the pipeline's own join. Each entry carries,
together: the official design row (offset, length, type, validation, content cell), the reviewed
semantic entry whose anchor passed the exact-anchor validator, the shipped field definition, and
the derivation code that produced it.

**The design-to-shipped join has been sitting inside the artefacts all along. No gate reads it.**

The census covered 32 manifests and 15,566 derivations, cross-checked against the shipped TOML on
eleven axes with zero disagreement except one modelo (below). Calibration reproduced four known
figures exactly, a negative control returned zero divergences on two axes where zero is true, and
a third path parsing the official markdown directly — bypassing the pipeline entirely — agreed.

## The result

**2,746 verified divergences over 15,438 fields — 17.8%.**

| axis | severity | population | divergences |
|---|---|---:|---:|
| type column → `signed` | fail-closed | 4,396 | **2,117** |
| type column → `data_type` | mixed | 15,339 | **606** |
| validation column → `required` | **fail-open** | 891 | **14** |
| content cell → `literal` | fail-closed | 968 | **9** |
| `offset`, `length`, `decimals`, digit extent | fail-closed | — | **0** |

The zeros matter as much as the counts. Where the design states a fact in a column the generator
reads, the corpus is exactly right. Four axes, tens of thousands of fields, no divergence.

## The mechanism, in one sentence

**The corpus is right exactly where the design is silent, and wrong exactly where the design
speaks.**

Routing splits on whether the design's content cell is blank:

- **Blank content** → the field is eligible for a reviewed render-profile rule → the rule declares
  the type explicitly → sign is derived correctly.
- **Stated content** → the field is ineligible → it falls to content-derived generation → `signed`
  is written as an unconditional literal.

So the modelo whose designs leave the content column empty ships 2,229 correctly-signed fields.
The modelo whose designs fill it in ships **zero**, across all four of its revisions. *The more
completely AEAT fills in its content column, the more certainly the pipeline drops the sign.*

This is visible inside a single modelo, which removes any "the two designs differ" defence: in one
modelo, 2,227 rows with a blank content cell ship signed, while 16 rows on one sheet with a filled
content cell ship unsigned — same modelo, same digest, same authority, same type, same width.

## The check that could have caught it, and why it did not

In a 17-byte slot the content cell says *"15 enteros y 2 decimales"* — seventeen digits. The
project's own authored rule says the signed type at width 17 means fourteen integer digits, two
decimals, and a sign position — also seventeen.

**Both sum to 17, so the one arithmetic check that inspects numeric extent passes.**

Two official columns contradict each other. The generator silently believes one, discards the
other, and reports nothing. Two mechanisms inside the same generator disagree about the same class
of field, and nothing compares them.

This sharpens the contract inconsistency: **the generator refuses when the design is unclear, and
stays silent when the design contradicts itself.** It raises on ambiguous content, unsupported
types, enumeration values outside the slot, constants that do not fit, digit counts that disagree
with the width — roughly sixty refusal sites. It assumes on sign, on required-ness, and on which
of two disagreeing columns to believe.

## Severity is not the same as size

**Sign fails closed.** The codec refuses to render a negative value into an unsigned field. So a
filing needing a negative in one of the 2,117 slots **fails loudly rather than emitting a wrong
figure**. The exposure is that the annual IVA summary — where negative adjustments are routine —
cannot emit a negative in any of its signed slots. Blocking, visible, safe.

**`required` fails open, and is worse per field.** Its rule maps three distinct facts to `false`:
the design said optional, the design said nothing, and the design used a token the matcher does
not know. Structurally: 1,646 fields never derive it at all (two paths hardcode it), 12 of 32
revisions have a completely empty validation column, and 94.3% of fields corpus-wide have no
validation value — on which the rule returns a confident `false`. **Roughly 12,900 fields ship
`required = false` as a fabricated default rather than a derivation**, and a missing mandatory
figure then renders as a clean, complete-looking record of zeros.

That the measured divergence count for `required` is only 14 is an artefact of the design rarely
stating the fact at all. It is the axis with the least evidence and the worst failure direction.

## The pattern generalises beyond these two axes

Several fields collapse "known value" and "never determined" into one representation: coordinates
and length (absence silently skips the entire shape check), value policy (same), padding and
justification (a legitimate "none" member doubles as "undetermined"), allowed values (open domain
versus never enumerated).

One field does it correctly and is the template: `decimals` is protected by a validator that
cross-checks it against the data type and refuses both halves — a decimal field without decimals,
and a non-decimal field with them. Absence is forced to mean exactly one thing.

**The generalisation:** every protected field is protected by a validator tying it to a *second*
field. `signed` and `required` are unprotected because the schema never imported the columns that
would ground them. The remedy is admitting the official source columns into the declaration so
cross-validation becomes possible — not richer scalar types everywhere.

## Clustering points at a cause

Divergences cluster hard by **derivation code**, not by modelo or revision. Three code paths
produce 96% of everything. The apparent "one modelo is fine, the rest are broken" split is fully
explained by which path a field takes.

Adjudication coverage is thin: of 2,117 sign divergences, **80 are adjudicated with recorded
evidence and 2,037 (96.2%) are unexamined**; of 14 `required` divergences, none is adjudicated.
And the 80 adjudicated ones reason that *"the representation therefore stands unchanged from the
surrounding run"* — where the surrounding run is the unexamined default. **The adjudication
inherits the defect rather than testing it.**

## The code's stated justification is factually wrong

A source comment and a currently-green test rest on the claim that one modelo's content cell
*"fills all seventeen bytes with no room for a marker"*, in contrast to another modelo which
spells the alternative form inline.

The asymmetry does not exist. That design carries a legend, repeated on every page, stating that
negative values carry the sign character in the first position. The other modelo carries no such
legend but spells it inline. **Each design states the convention once, in its own place.** And
decisively: the identical content string appears on 282 rows typed signed and 61 rows typed
unsigned in the same document — so that cell cannot be the statement of sign under any reading.

**The test's principle — sign is declared, never guessed from a token — is sound and must not be
relaxed. Its premise is false, and "declared" currently has no route for a field whose content
cell is populated.**

## One modelo, flagged by three independent instruments

A single modelo was surfaced separately by three lanes that shared no method:

- the divergence census: the only modelo whose provenance manifest disagrees with its shipped
  declarations (two fields missing, four extra, sixteen kind mismatches, both revisions);
- the cross-temporal audit: an inconsistent monetary pair, where one amount becomes free-text with
  space padding across a revision boundary while its sibling becomes a properly padded decimal —
  and a money total typed as free text cannot serialise as a fixed-width amount;
- the regeneration sweep: the only two revisions with real semantic drift, and the only two where
  check mode is never invoked at all. Its ledger states the shipped bytes are correct and the
  **inputs** are wrong.

Three instruments, one modelo. It is the highest-value single target in the corpus.

## Confidence

VERIFIED: the census and its calibration, negative controls and third-path corroboration; the
routing table probed by rendering; the arithmetic-check coincidence; the legend and content-string
evidence; the three-lane convergence.

INFERRED: that some unknown subset of the ~12,900 undefended `required = false` values is
materially wrong. It cannot be sized, because the design does not state the fact and no source in
this corpus does.

RETRACTED during this work, recorded so the numbers are not resurrected: a coordinate-based join
produced a confident 334 that was pure noise (the design has ten pages each restarting offsets at
1); a probe reported 202 ambiguity candidates where the true count was zero.

## Findings

- Across 15,566 field derivations, the official type column carries `N` on 4,396 rows; of those the
  shipped declaration says unsigned on 2,117 and signed on 2,279.
- The design states a validation value on 891 derivations; it is silent on 94.3%, and 12 of 32
  revisions have a completely empty validation column.
- `required` folds three distinct facts — said optional, said nothing, unrecognised token — into
  `false`, so roughly 12,900 fields ship a fabricated default.
- Sign fails closed at the codec; required fails open. Severity does not follow population size.
- The type column is not a controlled vocabulary: 579 derivations carry a spelled-out word or a
  non-type (`Numérico`, `Alfanumérico`, `Alfabético`, `No consta`, `Blancos`).
- Modelo 347 is flagged independently by three instruments and carries no `N` or `Num` field.

## Sources

- `dev/registry/pipeline/_export_tree.py` — the `signed=False` literals and `_is_required`
- `dev/registry/pipeline/render_profile.py`, `dev/registry/pipeline/render_profile_eligibility.py`
- `src/cadrumo/domain/calculations/registry/fixed_width_codec.py` — the fail-closed sign refusal
- `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/export/_generation.provenance.json`
