---
step_id: "S626,S627,S628,S629,S630,S631"
date: 2026-05-31
modified: '2026-05-31'
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W16.P48 S626-S631

## Steps executed

**S626** — `errors/_registry.py:219`: replaced prose `# deferred; no code available yet` with `CAST-RATIONALE-REGISTRY-DEFERRED-BINDING` marker explaining the circular-import window contract. Grep-post: zero prose-only `# deferred` adjacent to `# type: ignore` in that file.

**S627** — `providers/_base.py:242,252`: attached `CAST-RATIONALE-DYNAMIC-CLASSVAR-PROBE` inline markers on both `verification_source` and `provisional_pending_specimen` dynamic ClassVar probe lines. Grep-post: 2 occurrences of the token confirmed.

**S628** — `core/test_profile.py:127`: eliminated `pytest.skip(...)` by restructuring `test_project_answers_raises_before_registration` to use `subprocess.run` with a fresh Python interpreter, guaranteeing process-isolation without a skip gate. Design choice: subprocess fixture (option a). Grep-post: zero `pytest.skip(` in the file.

**S629** — `modelo/test_taxation_comparison.py:293`: M303 2025 3T snapshot confirmed available at runtime; removed `try/except + pytest.skip` guard, test now exercises the real snapshot path directly. Design choice: direct real-path test (option a). Grep-post: zero `pytest.skip(` in the file.

**S630** — `test_singletons.py:69,98`: strengthened `test_topics_singleton_loads_real_catalogue` with `isinstance(result, TopicCatalogue)` + `len(result.topics) > 0`; strengthened `test_legal_parameters_singleton_loads_real_mapping` with `isinstance(first_value, LegalParameter)` typed value assertion.

**S631** — Created `src/aeat/test_w16_p48_closure.py`: 18 real-behavior assertions covering S620-S630 closure contracts plus 4 prior-wave inventory ratchet invocations (utf8, cast-rationale, latin1, enum-constant). All 18 tests pass.

## Pytest outcome

- `test_w16_p48_closure.py`: 18/18 passed
- `test_singletons.py`: 8/8 passed
- `test_profile.py::test_project_answers_raises_before_registration`: 1/1 passed
- `test_taxation_comparison.py::test_comparison_error_raised_for_non_m100_snapshot`: 1/1 passed

## Collision signal

No conflicts. All 5 target files were clean at dispatch time. coder-alpha20 touched S620-S625 files only.

## Commit

SHA: `59b2085c4`
