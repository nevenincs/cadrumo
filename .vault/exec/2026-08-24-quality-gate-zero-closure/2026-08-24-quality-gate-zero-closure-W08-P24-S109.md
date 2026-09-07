---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:9d0a7e60b05871c37ddbe0407f497667a782ee7818229903ffb66bed87b20f23'
step_id: 'S109'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---

# Land the subsuming-disjunction detector: an assertion whose or-operands share one haystack and where one needle contains another is exactly the weaker operand, so the specific claim is never required (Terra xhigh fixes and refactors)

## Scope

- `dev/quality/`

## Changes

- `A` `dev/quality/subsuming_disjunctions.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py`
- `verify:` `uv run --no-sync python -c <real-tree and synthetic detector probes>` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 -m '' src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py::TestSilentResume::test_valid_session_resumes_with_no_authentication -rs` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/subsuming_disjunctions.py src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py` -> `pass`

## Notes

The exact live-tree sweep examined 3,972 test modules and failed on the one
known residual before repair. Removing the quoted-needle branch strengthens
the assertion; it is not reported as a defect fix because the behavioural test
skips on this host when the Windows credential store refuses the probe write.
