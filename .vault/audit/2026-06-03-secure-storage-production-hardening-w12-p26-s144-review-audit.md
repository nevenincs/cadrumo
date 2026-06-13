---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S144]]'
---

# `secure-storage-production-hardening` `W12.P26.S144` Review

## S144-001 | PASS | Local provider refusals are localized

The local filesystem provider previously raised hard-coded English messages across validation, sidecar, payload I/O, not-found, integrity, corruption, and delete paths.

Resolution: those paths now carry literal `translated_message` keys and structured contexts. The keys are present in `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` and pass the canonical locale audit.

## S144-002 | PASS | Probe cleanup failures are no longer silent

The probe cleanup path previously used `contextlib.suppress(...)` around sentinel deletion. That hid cleanup failures entirely.

Resolution: cleanup now catches only the expected filesystem/storage permission errors, logs a sanitized debug line naming the error type, and continues because cleanup failure is not the probe's primary result.

Reviewer follow-up: probe report details were also tightened so they no longer embed raw local paths or OS exception strings.

## S144-003 | PASS | Tests exercise real filesystem behavior

The updated tests write real payload and sidecar files under `tmp_path`, then assert localized errors for validation refusal, malformed sidecar shape, and sidecar byte-length corruption.

## S144-004 | PASS | Low-level OS/JSON causes are not chained through translated boundary errors

The review pass noted that low-level OS exceptions could carry raw path strings through `__cause__` chains even when the rendered operator message was localized. The local provider now raises the translated storage-boundary errors without preserving those raw causes. Structured diagnostic context remains available for the central redaction boundary.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_local.py src/aeat/adapters/outbound/storage/test_factory.py -k "local or factory"` passed with 28 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_local.py` passed with 21 tests.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/_local.py src/aeat/adapters/outbound/storage/test_local.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed after removing stale `cli.ledger.link.*` extras through `python -m aeat.locales remove`.

Disposition: close `AFR-042` as `remote-mirror`.
