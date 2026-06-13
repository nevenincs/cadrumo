---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` `Wave 2` `Modelo 111 filing linkage`

Extended the Modelo 111 registry foundation into application filing and export
behaviour while removing profile-side modelo shadow metadata from the filing
runtime.

- Modified: `src/aeat/application/filing/test_filing.py`
- Modified: `src/aeat/application/filing/test_export.py`
- Modified: `src/aeat/application/filing/_import.py`
- Modified: `src/aeat/application/filing/_complementaria.py`
- Modified: `src/aeat/application/filing/runtime.py`
- Modified: `src/aeat/application/filing/testing.py`
- Modified: `src/aeat/application/filing/_testing_registry.py`
- Modified: `src/aeat/domain/filing/_protocols.py`
- Modified: `src/aeat/domain/submission/_repository.py`
- Modified: `src/aeat/entrypoints/cli/filing/__init__.py`
- Modified: `src/aeat/entrypoints/cli/filing/test_filing_cli.py`
- Modified: `src/aeat/domain/submission/_engine.py`
- Modified: `src/aeat/adapters/outbound/aeat/export/test_engine.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Modelo 111 now has application-level behaviour coverage proving the filing
builder computes casillas 28 and 30 from the committed registry snapshot, the
registry export layout round-trips those calculated values from the written
payload, export verification reports a match for the approved draft, and
approval persists a registry schema/formula fingerprint.

The filing profile protocol and concrete runtime profile no longer carry
`applicable_modelos`. Justificante import and complementaria draft construction
therefore cannot stamp modelo applicability into taxpayer profile metadata.
Modelo applicability remains registry truth.

The filing CLI complementaria path now loads submitted filings through
`SubmissionRepository`, matching the encrypted submission store used by the
import path. The CLI test fixture persists submissions through the same
repository instead of writing plaintext JSON.

The read-only submission engine now also uses `SubmissionRepository` for
historical submission reads and listing. The older plaintext JSON history path
is not retained.

The justificante period normalizer now names the official period value as a
period code, avoiding a false security signal around the annual `0A` code.

Export verification now treats malformed registry export payloads as a
`MISSING` verification result instead of leaking parser exceptions. This keeps
the operator-facing verify contract closed and deterministic.

## Tests

- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_registry_schema.py src\aeat\application\filing\test_filing.py src\aeat\application\filing\test_export.py src\aeat\entrypoints\cli\filing\test_filing_cli.py src\aeat\adapters\outbound\aeat\export\test_engine.py -q` passed, 78 tests.
- `uv run ruff check src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\application\filing\_import.py src\aeat\application\filing\_complementaria.py src\aeat\application\filing\runtime.py src\aeat\application\filing\testing.py src\aeat\application\filing\_testing_registry.py src\aeat\domain\filing\_protocols.py src\aeat\domain\submission\_repository.py src\aeat\application\filing\test_filing.py src\aeat\application\filing\test_export.py src\aeat\entrypoints\cli\filing\__init__.py src\aeat\entrypoints\cli\filing\test_filing_cli.py` passed.
- `uv run ty check src\aeat\domain\calculations\registry src\aeat\application\filing src\aeat\entrypoints\cli\filing` passed.
- `uv run ruff check src\aeat\domain\submission\_engine.py src\aeat\adapters\outbound\aeat\export\test_engine.py src\aeat\entrypoints\cli\filing\__init__.py src\aeat\entrypoints\cli\filing\test_filing_cli.py src\aeat\application\filing\_export.py src\aeat\application\filing\test_export.py src\aeat\application\filing\test_filing.py` passed.
- `uv run ty check src\aeat\domain\submission\_engine.py src\aeat\adapters\outbound\aeat\export\test_engine.py src\aeat\entrypoints\cli\filing\__init__.py src\aeat\entrypoints\cli\filing\test_filing_cli.py src\aeat\application\filing\_export.py src\aeat\application\filing\test_export.py src\aeat\application\filing\test_filing.py` passed.
