---
step_id: "S654"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-06-01
modified: '2026-06-01'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-28-codebase-solidification-adr]]"
---

# codebase-solidification W26.P55 — S654, S655, S656

## Steps closed

- S654: `test_type_ignore_rationale_inventory.py` — ratchet created
- S655: Convention docstring documenting `TYPE-IGNORE-RATIONALE-*` embedded in S654 module head
- S656: `test_w26_p55_closure.py` — aggregate closure test created

## Files created

- `/src/aeat/test_type_ignore_rationale_inventory.py` — S654/S655 ratchet
- `/src/aeat/test_w26_p55_closure.py` — S656 aggregate closure

## Files modified (drift fixes — pre-existing ratchet failures from peer campaigns)

- `/src/aeat/test_any_param_rationale_inventory.py` — updated 11 stale line numbers in `_KNOWN_VIOLATING_LINES` after peer campaigns shifted function positions in `browser/session.py`, `_google_drive.py`, `_borrador_100.py`, `_censo.py`, `_snapshot_base.py`
- `/src/aeat/entrypoints/cli/_doc_reference.py` — added `from aeat.core.external_constants import UTF_8_ENCODING` import; replaced 3 bare `encoding="utf-8"` literals (lines 643, 652, 707 pre-fix) with `encoding=UTF_8_ENCODING` to satisfy the W11 UTF-8 enrollment ratchet
- `/scripts/gen_api_stubs.py` — added `_UTF_8: Final[str] = "utf-8"` local constant (per scripts-tree convention); replaced 1 bare literal at line 328

## Allowlist size

99 pre-existing `# type: ignore` sites enrolled in `_KNOWN_VIOLATING_LINES`.

Total `# type: ignore` sites in production code: 103.
Sites already carrying a rationale marker: 4.
Sites without a marker (enrolled for paydown): 99.

## Pytest outcome

10 tests collected and passed:

- `test_type_ignore_rationale_inventory.py::test_no_new_type_ignore_without_rationale` PASSED
- `test_w26_p55_closure.py::test_s654_type_ignore_rationale_inventory_importable` PASSED
- `test_w26_p55_closure.py::test_s655_docstring_documents_convention` PASSED
- `test_w26_p55_closure.py::test_s654_ratchet_passes` PASSED
- `test_w26_p55_closure.py::test_prior_wave_utf8_enrollment_inventory` PASSED
- `test_w26_p55_closure.py::test_prior_wave_cast_rationale_inventory` PASSED
- `test_w26_p55_closure.py::test_prior_wave_latin1_encoding_constant_enrollment` PASSED
- `test_w26_p55_closure.py::test_prior_wave_enum_constant_extraction_inventory` PASSED
- `test_w26_p55_closure.py::test_prior_wave_any_param_rationale_inventory` PASSED
- `test_w26_p55_closure.py::test_prior_wave_mock_inventory` PASSED

## G7 standing review gate (S655 note for follow-up curation)

Every `# type: ignore` in production code must carry a `TYPE-IGNORE-RATIONALE-<scope>` token within 3 lines, or be enrolled in `test_type_ignore_rationale_inventory.py` allowlist for paydown in a successor wave.
