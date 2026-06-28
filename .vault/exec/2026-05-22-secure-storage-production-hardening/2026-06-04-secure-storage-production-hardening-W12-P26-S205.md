---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S205'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s205-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S205`

Closed `AFR-103` for the evidence bundle service.

## Description

- Reviewed `src/aeat/application/evidence/_service.py` against the
  `manifest-discovery` classification for encrypted bundle manifests and
  operator-directed ZIP export.
- Verified bundle manifests persist through `EvidenceBundleRepository`, a
  `SecureBoundRepository` using the registered evidence bundle namespace.
- Replaced local UTF-8 literal use in manifest ZIP payload serialization with
  `UTF_8_ENCODING`.
- Replaced raw evidence not-found and verification failure exception messages
  with registered `translated_message` keys and structured context.
- Updated evidence tests to assert typed exception metadata instead of English
  message fragments.

## Outcome

`AFR-103` is closed. Evidence bundle manifest persistence remains encrypted and
bucket scoped, while the retained plain-file ZIP export remains
operator-directed and does not mutate the secure catalogue. User-facing evidence
errors now resolve through the core localized error envelope.

Validation passed:

- `uv run --no-sync -q ruff check src/aeat/application/evidence/_service.py src/aeat/application/evidence/_models.py src/aeat/application/evidence/test_evidence.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q pytest -q src/aeat/application/evidence/test_evidence.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The ZIP export path is a deliberate plaintext export surface: it writes only to
the operator-supplied `output_path`, writes record payload entries before
`manifest.json`, and is covered by a test proving it does not mutate the secure
catalogue. No direct production `SecureObjectRepository` construction, naked
environment access, silent exception swallowing, `noqa`, `pragma`,
monkeypatches, fakes, mocks, skips, or xfails were introduced.
