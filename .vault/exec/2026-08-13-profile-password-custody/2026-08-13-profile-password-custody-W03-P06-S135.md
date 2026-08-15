---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
step_id: 'S135'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh name the capsules root path in the retired-custody refusal

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/_capsule_discovery.py`

## Description

- Add the store location to a refusal that named the retired member but never
  where it was found.

## Outcome

The refusal now names the store it tells the operator to reset. Previously it
reported which retired member had been detected and withheld the location, so an
operator was instructed to destructively reset a store whose path the message
did not give.

The fix preserves every constraint the governing decision imposes. The capsules
root is not a bucket and not an identity, and naming it requires no inference
from retired content and no parsing of it — which is what made this a one-field
improvement rather than a weakening of the existence-only detection rule.

## Notes

This came out of a ruling that went the other way. The whole-store blast radius
was challenged as possibly incidental, and the investigation found it deliberate
on both axes: the decision names the store as the remediation unit, and the
detector withholds the offending bucket ON PURPOSE, because identifying it would
mean inferring a retired profile from retired content — which the same decision
forbids in the breath that mandates existence-only detection.

So the radius derives from the no-inference rule rather than from how the scan
happens to walk, and the operator's inability to enumerate profiles to find the
offender is coherent rather than harsh: under this regime the sanctioned remedy
is a reset of the whole store, so there is nothing to find.

What survived that ruling is exactly this gap. Everything about the refusal was
deliberate except that it told the operator to reset something without saying
what. Confirming the design before improving it is what kept the improvement to
one field instead of an argument about the design.
