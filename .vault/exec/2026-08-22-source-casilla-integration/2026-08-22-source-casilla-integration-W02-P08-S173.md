---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:c2842095269b6c2f645904a77b602bfe0191bea03b7d73aa139ba5b840cdb56f'
step_id: 'S173'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# carry typed row-source identity coordinates through ModeloBindingValue filing state

## Scope

- `src/cadrumo/domain/filing/_schema.py`

## Description

- Add an optional typed row-source identity to row-indexed filing binding values.
- Enforce 1-based row and source-kind coordinate agreement while retaining unidentified M720 rows.
- Redact identities from ordinary dumps, representations, and validation errors and expose an explicit secure projection.
- Bind identities into draft content addressing and encrypted filing-draft persistence.
- Hard-cut the filing-draft secure namespace to version 2 and validate direct and prepared writes identically.
- Add schema, confidentiality, encrypted roundtrip, prepared-write, stale-id, and M720 regression coverage.

## Outcome

`ModeloBindingValue` can now retain the canonical `RowSourceIdentity` beside one exact binding/row coordinate. Scalar identities, non-positive rows, and source-kind divergence fail closed; an absent identity remains an explicit valid state for unchanged M720 rows.

Ordinary serialization and representations omit opaque identities and fingerprints. The secure filing-draft writer and prepared batch writer use the explicit identity-preserving context, and the draft content address commits the same identity state. Filing-draft storage is version 2, so older persisted envelopes refuse rather than silently loading under the changed shape.

Independent review reported zero findings. The owner suite passed 56 tests, the reviewer suite passed 52, and Ruff and ty were clean.

## Notes

Scope expanded minimally into the filing-draft repository and namespace registry because the original generic writer dropped the excluded identity while the draft hash retained it. Both direct and prepared writes now share one durable content-address guard. S174 still owns application replay propagation, S175 owns CLI projection, and S176 owns inventory cohort expansion.
