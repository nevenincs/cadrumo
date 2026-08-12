---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:3a8d04b5be6a8b037ae0a7c54056a792e3c1d6d93b8b05d9b33573a3d8324b9a'
step_id: 'S37'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Decline the certificate alta-date field on unavailable grounding

## Scope

- `src/cadrumo/domain/censo/_certificado.py`
- `src/cadrumo/adapters/inbound/censo/_parser.py`
- Read-only. No production file changed.

## Description

- Confirm no issued Certificado de Situación Censal (G313) specimen exists
  anywhere in the tree, including fixtures and corpus directories.
- Search the bundled RGAT (RD 1065/2007) consolidated text for the
  certificate's physical content.
- Search the bundled AEAT Modelo 036 "Folleto de Censos" brochure for the
  same.
- Decide whether to add an alta-date field to `CertificadoSituacionCensal`
  on what that search establishes.

## Outcome

Closed on measurement, not on code. Neither authority in the tree grounds the
claim either way.

RGAT arts. 70-71 and 144-146 establish that "situación censal" is a
certifiable fact and describe the correction procedure, but neither those
articles nor any other bundled normative text itemizes the physical fields a
G313 artifact prints. The bundled Modelo 036 brochure covers identification
and Cl@ve access, not certificate layout. No issued specimen exists in this
tree to read directly — the parser's own docstring already records that
today's extraction is unpinned for that reason.

Per the grounding rule, a parser field for a line whose presence on the
document is unconfirmed is worse than the current gap, so the field is NOT
added. `CertificadoSituacionCensal` and its structurally-unpinned parser stay
as they are; the model's docstring already frames the absence as unmeasured
rather than confirmed-absent, which remains the accurate framing after this
pass, so no doc correction was needed either.

The disconfirming clause this row was written with — whether a stated alta
date would attach to the censal registration rather than to the economic
activity — was never reached, because the antecedent (whether the document
states an alta date at all) is itself unconfirmed. It is recorded as unreached
rather than as answered.

This does not touch the standing remedy: the profile's self-declared
activity-start date, when it grounds a first-period zero on the
compensación, is surfaced as resting on an unverified declaration through the
uncontrasted reason-identity already live on the wallet gate. That advisory
stays the durable posture until a real specimen changes what can be
confirmed.

## Notes

Genuinely open, not closed-by-narrowing: acquiring a real issued G313
specimen (through the encrypted evidence path) or a corpus source
reproducing its printed layout would reopen this question with new evidence.
Until then, no parser field, no contrast gate, and no obligation-start-year
read may be derived from this document. A future attempt to add such a field
must re-run this same grounding check rather than rely on this note as
clearance.
