---
step_id: S162
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-28-codebase-solidification-W01-P07-S161]]"
---

# codebase-solidification W01.P07.S162 — real-behaviour tests for InputKind enum surface

## Outcome

Created `src/aeat/application/filing/test_init.py` with 9 real-behaviour tests (markers: `unit`, `domain_application`) asserting every former bare-string `input_kind` comparison produces the same boolean truth value under the `InputKind` enum surface.

Tests:

- `test_input_kind_members_equal_their_string_values` — StrEnum contract: each member == its TOML literal.
- `test_input_kind_is_a_str` — all members are `str` instances.
- `test_computed_casilla_comparison_produces_same_truth_as_bare_string` — real modelo-130 snapshot; every formula-targeted casilla is `InputKind.COMPUTED` and `== "computed"` yields identical boolean.
- `test_manual_casilla_comparison_produces_same_truth_as_bare_string` — real modelo-130; required manual casillas satisfy `InputKind.MANUAL`.
- `test_bound_casilla_comparison_produces_same_truth_as_bare_string` — real modelo-130; binding-linked casillas satisfy `InputKind.BOUND`.
- `test_non_computed_casilla_filter_produces_same_set_as_bare_string` — set equality between `!= InputKind.COMPUTED` and `!= "computed"`.
- `test_tuple_membership_with_enum_members_matches_bare_string_tuple` — `(InputKind.MANUAL, InputKind.BOUND)` vs `("manual", "bound")` set equality.
- `test_set_membership_with_enum_members_matches_bare_string_set` — `{InputKind.COMPUTED, InputKind.INFORMATIONAL}` vs string set equality.
- `test_informational_casilla_comparison_produces_same_truth_as_bare_string` — real modelo-303 snapshot; informational casillas satisfy `InputKind.INFORMATIONAL`.

No mocks, no skips, no xfail, no tautological assertions. All comparisons use real registry authority against bundled TOML data.

## Files touched

- `src/aeat/application/filing/test_init.py` (new)

## Verification

- `uv run --no-sync pytest src/aeat/application/filing/test_init.py -xvs` → 9 passed
- Commit: `1aeb3aa41`
