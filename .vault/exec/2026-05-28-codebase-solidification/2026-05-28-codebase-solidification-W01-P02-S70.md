---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S70'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W01.P02.S70`

Created `src/aeat/domain/normatives/test_init.py` with a real-behavior subprocess test asserting that `import aeat.domain.normatives` produces no stdout output.

- Created: `src/aeat/domain/normatives/test_init.py`

## Description

Test spawns a fresh Python subprocess running `import aeat.domain.normatives`, captures stdout, and asserts it is empty. Uses `subprocess.run` with `capture_output=True` — no mocks, no capsys shortcuts that could mask subprocess output. Also asserts `returncode == 0`.

## Tests

`pytest src/aeat/domain/normatives/test_init.py -xvs` passes: 1 passed in ~1.95s.
