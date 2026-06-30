---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S22'
related:
  - '[[2026-06-30-cli-persona-testimonials-plan]]'
---

# W04.P08.S22 Justificante Capture Matching And Evidence Stamping

Scope: live justificante capture snapshot validation and local filing-evidence stamping.

## Description

RAG grounding:

- `uvx vaultspec-rag search "justificante capture matching evidence stamping csv tax id period modelo expediente" --type code`
- `uvx vaultspec-rag search "justificante capture snapshot pdf_sha256 bucket event payload_version evidence stamped" --type code`

Official grounding used AEAT presented-declaration and justificante-copy surfaces:
the local capture must bind a downloaded receipt to the selected taxpayer, model,
year, period, expediente, CSV, and PDF bytes before stamping local filing evidence.

The snapshot model now rejects a mismatched `pdf_sha256` instead of trusting a
declared hash. The evidence-stamped bucket event now records `source_kind`,
`pdf_sha256`, `captured_at`, and `expediente_id`; because the event payload
contract changed, `MODELO_LIVE_EVIDENCE_STAMPED` payload version was bumped to 2.
The overview calendar test helper now derives snapshot hashes from fixture bytes.

## Outcome

Changed:

- `src/aeat/application/live/_justificante.py`
- `src/aeat/application/live/tests/test_justificante_capture.py`
- `src/aeat/application/live/tests/test_justificante_capture_stamp.py`
- `src/aeat/application/overview/tests/test_calendar_filing_evidence.py`

Review found one cross-suite helper regression and one payload-version issue; both
were fixed and rechecked. Residual design note: richer evidence provenance remains
on secure snapshot and event payload, not on the compact `ExternalEvidence` value.

## Verification

Passed:

- `uv run --no-sync pytest -p no:cacheprovider src/aeat/application/live/tests/test_justificante_capture.py src/aeat/application/live/tests/test_justificante_capture_stamp.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q` -> 48 passed before the later unrelated source-catalogue baseline regression.
- `uv run --no-sync pytest src/aeat/application/overview/tests/test_calendar_filing_evidence.py -q` -> 31 passed in the S22 fallout run.
- `uv run --no-sync pytest src/aeat/application/live/tests/test_justificante_capture.py src/aeat/application/live/tests/test_justificante_capture_stamp.py -q` -> 17 passed in the S22 fallout run.
- W04 touched-file ruff gate in isolated latest-HEAD worktree passed.

Latest isolated retest note: collection of `test_calendar_filing_evidence.py`
is now blocked on clean `HEAD` by baseline registry source byte-count mismatch
`boe-modelo-210-base-order`, proven in a no-W04 baseline worktree.

