---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W06.P19.S113'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-convention-hardening-audit]]'
---

# declaracion-extraction-architecture W06.P19.S113

Converted declaration-extraction and shared inbound-PDF user-facing error
strings to `tr()` locale keys, then synchronized the locale catalogues through
the project locale CLI.

- Modified: `src/aeat/adapters/inbound/declaracion/_parser.py`
- Modified: `src/aeat/adapters/inbound/pdf/_pdfplumber.py`
- Modified via `python -m aeat.locales`: `src/aeat/locales/ca.yml`
- Modified via `python -m aeat.locales`: `src/aeat/locales/en.yml`
- Modified via `python -m aeat.locales`: `src/aeat/locales/es.yml`
- Modified via `python -m aeat.locales`: `src/aeat/locales/hu.yml`
- Import-boundary fix: `src/aeat/domain/justificante/__init__.py`

## Description

The parser now routes conflict, unresolved-period, unresolved-tax-id,
registry-snapshot, profile-selection, template-detection, and extraction
failure messages through `aeat.core.i18n.tr()`. The shared PDF helper now routes
missing-file, pdfplumber-open, and no-text errors through `tr()` as well.

Locale changes were applied with:

- `uv run --no-sync python -m aeat.locales scaffold`
- `uv run --no-sync python -m aeat.locales scaffold --sync-locale-parity`

The second command was required because the worktree locale CLI now audits
dynamic-namespace parity. It filled missing Hungarian dynamic-namespace parity
placeholders in addition to the concrete declaration/PDF keys.

While verifying this slice, importing the PDF error root exposed an eager
`aeat.domain.justificante` package import of `JustificanteRepository`, which
pulled secure-storage crypto/sql modules into a partially initialized cycle.
`JustificanteRepository` is now lazy on the package surface so declaration/PDF
error imports stay lightweight. A direct `JustificanteRepository` import still
exposes a separate storage crypto/sql cycle and remains tracked by `W06.P19.S120`.

## Tests

- `uv run --no-sync python -m aeat.locales audit`
- `uv run --no-sync ruff check src\aeat\domain\justificante\__init__.py src\aeat\adapters\inbound\declaracion\_parser.py src\aeat\adapters\inbound\pdf\_pdfplumber.py src\aeat\adapters\inbound\declaracion\test_parser_boundary.py src\aeat\adapters\inbound\declaracion\test_exception_hygiene.py src\aeat\adapters\inbound\declaracion\test_shared_model_boundaries.py src\aeat\domain\calculations\registry\test_exception_hygiene.py src\aeat\domain\calculations\registry\test_modelo_840_registry.py src\aeat\locales\cli.py src\aeat\locales\manager.py src\aeat\locales\test_parity.py`
- `uv run --no-sync pytest -x src\aeat\adapters\inbound\declaracion\test_parser_boundary.py src\aeat\adapters\inbound\pdf\test_shared.py src\aeat\adapters\inbound\declaracion\test_exception_hygiene.py src\aeat\adapters\inbound\declaracion\test_shared_model_boundaries.py src\aeat\domain\calculations\registry\test_exception_hygiene.py src\aeat\domain\calculations\registry\test_modelo_840_registry.py src\aeat\locales\test_parity.py -q`
