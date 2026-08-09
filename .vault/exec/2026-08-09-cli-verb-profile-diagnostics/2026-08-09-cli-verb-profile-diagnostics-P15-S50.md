---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:66fd14532cdaed20d7d26790ac303c0e683b072959e1afa35ee7bcfa0b00c3c5'
step_id: 'S50'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Census every operator-facing message that instructs the operator to supply a profile value, independently of whether it names an identifier, and classify each hit

## Scope

- `src/cadrumo/locales/en.yml`

## Description

- Built a census keyed on BEHAVIOUR rather than on identifier shape: every catalogue string carrying an instruction verb together with a profile noun, regardless of whether any identifier appears in it.
- Classified each hit into three buckets: names its field through a placeholder, names it by raw dotted identifier, or names it in prose only.

## Outcome

Both honesty reviews named this class as explicitly unmeasured, in the same words: a message naming a field in prose without a dot could not be caught by either review's census, nor by the campaign's own, because all three keyed on dotted tokens. This Step measures it.

**59 profile-instruction messages. 22 carry a placeholder. 0 carry a raw dotted identifier. 37 name things in prose only.**

The zero is the headline: no operator-facing instruction to supply a profile value still names its field by a raw dotted identifier. That is the campaign's central claim, and it is now measured by a method that does not presuppose the defect's shape.

The 37 prose-only hits were read individually rather than counted. The large majority name no profile field at all and are correctly prose: storage-integrity errors, help text, archive descriptions, and messages naming environment variables or CLI flags, which the operator types literally and which would be actively wrong to replace with a schema label.

Three hits do name a specific field or claim one is missing, and each is dispositioned in its own Step: two censal fiscal-ID refusals, and one registered error carrying an unactionable message.

The method is the durable part. A dotted-token census can only find the defect it already knows the shape of; this one starts from what the message DOES to the operator, which is why it could measure a class three previous censuses could not.

## Verification

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

The census itself is the instrument, and its own controls are the two non-empty buckets: it finds the 22 messages this campaign grounded and correctly reports zero remaining raw identifiers, so a run reporting zero everywhere would be visible as a broken instrument rather than a clean result.

## Notes

Swept the English catalogue, as the reviews' censuses did. The locale parity gate means a key present in one catalogue is present in all four, and this campaign authored every translation of the messages it changed, so the finding transfers - but the prose of a translation is not mechanically checked against its English counterpart by anything here.
