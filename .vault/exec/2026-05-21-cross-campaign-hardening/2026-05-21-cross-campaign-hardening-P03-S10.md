---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P03.S10'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P03.S10`

Closed XDOM-2 for `application/workflow/_engine.py`: the workflow
engine no longer imports concrete outbound AEAT adapter classes or
live Sede walkers.

- Modified: `src/aeat/application/workflow/_engine.py`
- Modified: `src/aeat/application/workflow/_protocols.py`
- Modified: `src/aeat/application/workflow/_adapters.py`
- Modified: `src/aeat/application/workflow/test_engine.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Moved the Sede source callable contracts into workflow protocols and
made `_engine.py` consume those callables as injected ports. The live
`walk_expedientes_tree` and `fetch_notifications_query` wiring now
lives in `_adapters.py`, which is the production composition boundary.

Re-pointed draft status checks to the shared `domain.submission`
`ModeloDraftStatus`, replaced adapter certificate-health enum usage
with local severity values, and removed the engine's concrete
site-health adapter import. Added an architecture regression that parses
`_engine.py` imports and fails if outbound AEAT adapter imports return.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/application/workflow/_engine.py src/aeat/application/workflow/_adapters.py src/aeat/application/workflow/_protocols.py src/aeat/application/workflow/test_engine.py src/aeat/application/workflow/test_adapters.py src/aeat/application/workflow/test_profile_health.py` passed.

`uv run pytest -q src/aeat/application/workflow/test_engine.py src/aeat/application/workflow/test_adapters.py src/aeat/application/workflow/test_profile_health.py` passed with 32 tests in 76.26s.

`rg -n "^from .*adapters\\.outbound\\.aeat|^import .*adapters\\.outbound\\.aeat|sede as _sede|CertificateHealthSeverity|from .*Expediente|from .*NotificationsSnapshot|from .*AeatSession" src/aeat/application/workflow/_engine.py` found no remaining concrete outbound-adapter imports in `_engine.py`.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S10` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P03-S10.md src/aeat/application/workflow/_engine.py src/aeat/application/workflow/_adapters.py src/aeat/application/workflow/_protocols.py src/aeat/application/workflow/test_engine.py` passed with the existing plan-file CRLF normalization warning.
