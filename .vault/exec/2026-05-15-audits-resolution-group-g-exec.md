---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-15'
modified: '2026-05-15'
step_id: 'G3'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-15-audits-resolution-exec]]"
---

# `audits-resolution` Group G closure

The prek gate is green. After Group F closed the type-safety mandate
but left the ruff backlog gating every commit behind `--no-verify`,
Group G partitioned the 85 outstanding diagnostics into two buckets
and closed both.

## Description

G1 (`d58a42dc`) added per-file-ignores for 60 structurally
unavoidable / domain-justified diagnostics: E402 deferred imports
inside circular-import-breaking package `__init__.py`s and a
handful of cross-cutting modules; RUF001 / RUF003 on Spanish-
typography corpus and label-regex files where the unicode is
load-bearing; S311 on the local-only PDF scrubber's non-crypto
random; and a long tail of S105 / S106 / S108 / S603 against
specific test fixtures and platform helpers whose synthetic
secrets / temp paths / subprocess invocations ruff misreads.
Every entry is scoped to a single file path; no project-wide
rule was relaxed.

G2 (`dcc350c8`) closed the 25 legitimate-defect bucket via
mechanical fixes across 19 files: six SIM115 bare-open calls
wrapped, five `_DECLARED_ERROR_CODES` aliases renamed to
UPPERCASE_SNAKE, three function-local var renames, two N818
exception renames threaded through the error registry
(`WorkflowAbortSignalError`, `CasillaConstraintViolationError`),
one test-class name fix, one decimal-alias canonicalisation,
three pytest.raises match strings tagged raw, one
typographic unicode swap, one nested-with collapse, two
overlong f-string splits. Zero `# noqa`, zero `# type: ignore`
introduced.

## Tests

- `uv run --no-sync ruff check src/` — `All checks passed!`
- `uv run --no-sync ty check src/` — `All checks passed!`
- `grep -rn "# type: ignore\|# pyright: ignore" src/ --include="*.py" | wc -l` — `0`
- `uv run --no-sync prek run --all-files` — every hook passes
- Smoke commit `b8438086` landed cleanly without `--no-verify`,
  reverted by `64e3bbfa`. The gate is confirmed-green for
  routine work.

Both Group F's F4 and Group G's G3 closure records sit alongside
the Group A–E exec stream under `.vault/exec/`. The branch is now
clear of the type-safety + lint-backlog gates that were blocking
commit hygiene at the start of the day.
