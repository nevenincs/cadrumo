---
tags:
  - '#audit'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:9e1244ec6a07f71ab97564e691c42012dcd744b55a2e46a2707ae01c0ab9a0c2'
related: []
---

# `semantic-consolidation` audit: `Bounds a field-annotation scan cannot see`

## What this records

This campaign's most productive instrument is a scan that reads pydantic field
ANNOTATIONS and reports where two models disagree about the same field. It has
found real defects: a currency alias that accepted `12A`, a filing snapshot that
accepted the single character `E`, a patch model that let an operator edit a row
into a state they could not create.

It also over-reports, systematically and in one direction. Three times in one
session a field looked unbounded to the scan and was not, because its bound lives
somewhere an annotation cannot express. Each was investigated as a suspected
defect and each turned out sound. Recording them so the fourth is recognised
faster, and so nobody "fixes" one by adding a second, weaker bound beside the
real one.

## The three shapes

### A bound expressed as a closed SET

`application/ledger/evidence_draft.py` carries `iva_rate: Decimal | None` with no
range at all, on a field its own docstring calls a whole-number percentage. The
scan reported it unbounded. It is not: every value passes through
`resolve_iva_rate_slot`, which maps against the closed `IvaRate` slot taxonomy
rather than a range.

Probed: `21` and `10` resolve; `210`, `-5` and `0.21` are refused with the
accepted set named. That last one matters -- `0.21` is the FRACTION-scale value
arriving on a percentage-scale path, and the closed set catches the scale
confusion a numeric range would have admitted.

A set is a stronger bound than a range here, not a weaker one.

### A bound enforced by the CODEC, keyed by declared width

`application/filing/_producer_snapshot.py` declares fixed-width export rows whose
every field is `str | None` -- `codigo_pais`, `ciudad`, `entero`, `decimal`,
identically unconstrained. These feed FILED BYTES, which made this the
highest-consequence open question in the campaign.

It is safe. `pad_fixed_width_text` refuses a value longer than the field's
registry-declared length, and `_render_record_bytes` independently refuses when
the encoded byte count does not equal the declared count. Two guards, both
failing closed.

Probed: `"ES"` renders into a 2-character field; `"ESPANA"` is refused with
`fixed-width value exceeds length 2`. It does not truncate, which is the failure
that would have mattered -- a silently shortened country code on a filed record.

The bound could not be on the row model even in principle: the width comes from
the registry record design, per modelo and per revision, and the row model is one
generated shape serving all of them.

### A policy carried by a shared VALIDATOR, not the annotation

`Modelo720RowObservation.currency_code` and `DonativoDonorObservation.country_code`
both look length-only. Both apply a shared `uppercase_alpha_code` validator that
REFUSES a lowercase code rather than folding it.

This one caused a real mistake. The Modelo 720 field was migrated to the
normalising canonical annotation, which layered a second and contradictory policy
over the shared validator its sibling `country_code` follows, and a test went red.
Reverted and declared.

## The rule this yields

Before treating an unbounded-looking field as a defect, look for the bound in
three other places: a closed set the value is resolved against, a codec or writer
that refuses on its own contract, and a `field_validator` on the same class.

And the direction of the mistake matters. Adding a bound to a field that already
has an invisible one is not harmless tidying -- it can contradict the real policy,
as the Modelo 720 case did. The annotation is not the only place a rule can live,
and a scan that assumes it is will keep proposing to move rules into it.

## What still needs a bound

The same session found genuinely unguarded fields, so the lesson is not "the scan
cries wolf". `PurchaseInvoiceEvidence` and its patch took any Decimal at all for
`taxable_base`, `iva_rate` and `iva_amount`, and the first two reach a renta
deductible-expense observation. Bounded, with the reason recorded on the record.

The difference between that case and the three above is only discoverable by
tracing the consumer. There is no shortcut that reads the field alone.
