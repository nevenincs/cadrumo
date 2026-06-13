---
step_id: S69
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
  - '[[2026-05-30-identity-primitives-reference]]'
---

# identity-primitives W05.P19.S69 — anti-tautology proofs and public-surface pin

## Scope

Close Wave 5 by demonstrating the anti-tautology property of
each landed detector and pinning the helper module's public
surface so silent removal of a detector cannot occur without
breaking the test contract.

## Outcome

Added four new tests:

- `test_sibling_domain_detector_flags_synthetic_violation` —
  constructs `tmp_path/src/aeat/domain/a/_consumer.py` importing
  from `domain/b/_ids.py`, runs the clause-1 detector, asserts
  the violation is reported with the alias name in the message,
  then rewrites the consumer to remove the import and asserts
  the detector reports clean. The two-phase shape is the
  anti-tautology proof: a passing assertion in the violation
  phase together with a passing assertion in the clean phase
  proves the detector discriminates rather than always-passing.
- `test_private_name_detector_flags_synthetic_violation` —
  same two-phase shape for clause 2 against a synthetic
  `application.x._consumer` importing `_HEX_EXAMPLE_LENGTH`.
- `test_hex_length_detector_flags_synthetic_violation` — same
  shape for clause 3 against a synthetic `domain.x._models`
  declaring `_HEX_EXAMPLE_ID_LENGTH = 64`.
- `test_detector_public_surface_is_pinned` — asserts
  `_identity_placement.__all__` matches the expected set of
  nine public names (`AEAT_ROOT`, `AliasInventory`, `Finding`,
  `build_alias_inventory`, `find_*` x4, `iter_aeat_modules`).
  Removing a detector accidentally breaks this test
  immediately.

The clause-4 anti-tautology proof landed under S68 as
`test_bare_str_typed_id_detector_recognises_synthetic_violation`
because the bare-`str` detector requires an alias inventory as
part of the fixture; the two-phase shape is the same.

## Verification

`uv run --no-sync pytest src/aeat/diagnostics/
test_identity_primitive_placement.py -v` runs nine tests
(9 passed, 5.14s). The default `pytest src/aeat/diagnostics/`
collection picks up `test_identity_primitive_placement.py`
without any pytest configuration changes — the module sits
alongside the existing diagnostics smoke tests and carries
the same `pytestmark = [pytest.mark.unit,
pytest.mark.domain_application]` markers required by the
project marker-integrity hook.
