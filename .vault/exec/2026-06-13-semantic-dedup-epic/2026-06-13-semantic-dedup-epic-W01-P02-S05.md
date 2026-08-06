---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-07-04'
modified: '2026-07-04'
body_hash: 'sha256:f1efbe524831d941f786b20d495b333743212b3d6be5bbe0a2a5601e443f0bf3'
step_id: 'S05'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

# Delete the dormant _formats currency encode/serialise/deserialise path and its tests, or record an explicit retention rationale if a near-term consumer is planned

## Scope

- `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py`

## Description

- Re-confirm tree-wide (grep) that the fichero-BOE `_formats` currency encode / serialise / deserialise stack (`_record_spec.py`, `_serialise.py`, `_deserialise.py`) has zero production consumers: the only references outside the package are docstring `See Also` cross-references and one `#:` comment in `core/external_constants.py`; there is no production import of any `_formats` symbol.
- Evaluate deletion against ADR F2 (deletion of the dormant stack is owner-gated) and the safety gates, and record an explicit retention rationale instead of deleting.

## Outcome

- The dormant `_formats` stack is RETAINED, not deleted, pending owner confirmation. Grep confirms the code is production-dead, but deletion is not taken autonomously for three grounded reasons.
- ADR F2 explicitly makes removal owner-gated: the stack is a roundtrip-tested encoder of the AEAT submission wire format, and deletion is gated on owner confirmation that no in-flight migration intends to adopt it. No owner confirmation is available to this run.
- The stack carries a durable roundtrip contract test (`_formats/tests/test_fichero_boe_roundtrip.py`) that is enrolled in the repository roundtrip-coverage gate (`src/aeat/tests/test_roundtrip_coverage.py`); deleting the stack would also require editing that safety gate, widening the blast radius beyond a dead-code removal.
- Deleting a roundtrip-tested AEAT wire-format encoder is a safety-relevant destructive action; per `aeat-safety-legal-gates` and the ADR owner-gating, the disciplined disposition is retain-and-document.

## Notes

- The plan step is satisfied by its explicit OR branch (delete if dead, or record a retention rationale). This is a deliberate retention with a recorded rationale, not a silent skip.
- Follow-up for the owner: confirm no in-flight migration will adopt the `_formats` explicit-spec encoder; on confirmation, the stack, its tests, and the `test_roundtrip_coverage.py` enrollment can be removed together in one atomic commit. Until then the wired registry-driven export path (`application.filing.export_draft` plus `registry.parse_export_payload`) remains the sole canonical export surface, as ADR F2 records.
