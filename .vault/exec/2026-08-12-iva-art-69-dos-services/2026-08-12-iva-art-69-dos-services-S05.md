---
tags:
  - '#exec'
  - '#iva-art-69-dos-services'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:3b534adb14e85aadcafa68eb51bcb3ec2ba9b8a4ae06b6bec8d052834af7be70'
step_id: 'S05'
related:
  - "[[2026-08-12-iva-art-69-dos-services-plan]]"
---

# Retract the electronically-supplied-services concern on the prior feature's records rather than leaving it standing. Art 70.Uno.4 locates e-services at the recipient only when the recipient is established in the TAI, art 70.Dos only ever pulls services INTO the TAI, and art 69.Dos names no e-services item - so the subject outcome for an outbound B2C e-service is correct. Correct the exec note and the ADR consequence that called it probably over-taxed

## Scope

- `.vault/`

## Description

- Retracted the electronically-supplied-services concern on the prior feature's
  exec record and ADR, in place, with the reading that closed it.
- Recorded that the prior carry-forward's surviving half is the art. 69.Dos
  list, modelled by this feature.

## Outcome

Done. The concern is withdrawn on both records rather than left standing beside
a decision that contradicts it.

## Notes

The retraction is worth more than the flag was. An honesty pass that raises a
concern and never resolves it leaves a later reader to re-derive the same
reading, and in the meantime the concern reads as a known defect. The reading
is three sentences: art. 70.Uno.4.º locates e-services at the recipient only
when the recipient is established IN the TAI, so it never reaches an outbound
supply; art. 70.Dos only pulls services INTO the TAI, so it can add Spanish
taxation and never remove it; and art. 69.Dos names no e-services item.

The flag was still the right move. The wider claim it made -- that art. 70's B2C
rules deserve reading alongside 69.Dos -- is exactly what reading them settled.
