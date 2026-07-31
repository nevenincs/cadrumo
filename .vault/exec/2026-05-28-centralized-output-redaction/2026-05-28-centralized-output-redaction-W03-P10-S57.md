---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-07-17'
body_hash: 'sha256:0aed2f020ccd97d235de271fd788a41b4ef511c7471435d96f70105c6ca383ff'
step_id: 'S57'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# W03.P10.S57 modelo CLI redaction expectations

Scope: audit and update modelo CLI tests for central identifier redaction expectations.

## Description

- Inspect modelo CLI tests for public profile, bucket, and tax identifier output expectations.
- Add a real JSON describe-output guard proving non-sensitive modelo metadata does not receive profile or bucket placeholders or UUID-shaped raw identifiers.
- Fix two real ruff `E741` findings in the touched file by replacing ambiguous loop variable names.

## Outcome

S57 is implemented for the current modelo CLI test surface.

## Notes

Discovery found no public CLI output assertion in this file that expects raw profile ID, bucket ID, or tax ID. Existing `bucket_id="default"` values are model-construction inputs, and `perceptor_nif` examples are typed parser/domain payload inputs rather than rendered public output.

Verification:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_modelo.py` passed.
- `uv run pytest -q src/aeat/entrypoints/cli/test_modelo.py` passed: 158 passed.
- Follow-up gates passed after strengthening the describe JSON guard with a UUID-shaped raw identifier scan.
