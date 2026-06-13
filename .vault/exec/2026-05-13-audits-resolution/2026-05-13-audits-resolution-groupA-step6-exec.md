---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-eliminate-shims-audit]]"
---

# audits-resolution group-a step-6

## scope

Plan row A6: excise the 12 transient-meta phrase violations the audit
flagged.

## edits

Twelve docstring / comment rewrites describing what the code IS
structurally rather than what it once was:

- `src/aeat/domain/calculations/registry/test_text.py` — drop
  "the previous `<[^>]+>` stripper regex"; describe the contract.
- `src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py`
  — drop "The previous implementation converted..."; describe why
  the fallback declines to materialise PEM/key files.
- `src/aeat/adapters/inbound/justificante/_extract.py` — drop
  "Stricter than the previous [0-9A-Z]{8,12} pattern"; describe
  the shape constraint and the "PRESENTADOR" exclusion semantically.
- `src/aeat/core/observability/_replay.py` — drop "Legacy flags
  removed from the workflow CLI surface"; describe the scrubber
  contract.
- `src/aeat/application/overview/__init__.py` — two UX-008 mentions
  rewritten to describe profile-completeness semantics.
- `src/aeat/application/overview/test_calendar.py` — UX-008 mention
  rewritten to describe the contract the test pins.
- `src/aeat/application/topics/__init__.py` — UX-015 mention
  rewritten to describe the operator need.
- `src/aeat/entrypoints/cli/_declaration.py` — UX-021 mention
  rewritten to describe the next-action contract.
- `src/aeat/entrypoints/cli/test_workflow_surface.py` — two UX-013
  / UX-021 mentions rewritten to describe the wiring under test.

The audit-allowlisted domain references survive (legal/AEAT history
in `core/identity/_tax_id.py`, `domain/invoices/test_validators.py`,
`adapters/inbound/sanitizer/_dynamic.py`).

The renta substrate's "Replaces the binding selector" docstring in
`src/aeat/domain/renta/_substrate.py:89` falls under the
concurrent-agent off-limits territory and is not in scope.

## verification

`ruff check` on every touched file: green.
`pytest src/aeat/domain/calculations/registry/test_text.py
src/aeat/application/overview/test_calendar.py` returns 34 passed.

The remaining "previously" / "historically" / "replaces" hits across
`src/aeat/` describe operator workflow state (runtime), AEAT/BOE
domain history, or the audit-allowlisted classes; they are not
transient code-history metadata.
