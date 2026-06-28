---
tags:
  - '#exec'
  - '#aeat-verify'
date: '2026-04-24'
modified: '2026-04-24'
related:
  - "[[2026-04-24-aeat-verify-plan]]"
  - "[[2026-04-24-aeat-verify-adr]]"
  - "[[2026-04-24-aeat-verify-research]]"
---



# `aeat-verify` `phase-1` `remote-domain-foundation`

Phase 1 of the `aeat-verify` plan lands the sealed, read-only
`aeat.remote` subpackage with every Tier-1 domain record, typing
Protocol, error type, and enum the ADR catalogues. No concrete
Playwright paths ship in this phase; the Phase 2 fetchers consume
the shapes created here. Every record carries the Layer 1
`mode: Literal["read"] = "read"` structural write-guard marker, and
the Layer 3 grep test walks the entire subpackage with no
whitelisting.

- Created: `src/aeat/remote/__init__.py` (sealed public API, alphabetical `__all__`).
- Created: `src/aeat/remote/_schema.py` (`RemoteCasilla`, `RemoteReceipt`, `RemoteFiling`, `RemoteExpediente`, `RemoteNotification`, `RemoteNavigationGraph`, `RemoteFilingRef`).
- Created: `src/aeat/remote/_status.py` (closed `RemoteFilingStatus` StrEnum + `classify_status` helper with `UNKNOWN` fallback and warning log).
- Created: `src/aeat/remote/_protocols.py` (`RemoteFilingFetcher`, `NotificationReader` runtime-checkable Protocols).
- Created: `src/aeat/remote/_errors.py` (`RemoteFetchError` hierarchy plus `RemoteParseError`, `RemoteNavigationError`, rooted at `aeat.core.errors.AeatError`).
- Created: `src/aeat/remote/filings/__init__.py`, `src/aeat/remote/filings/_filing_detail_130.py`, `src/aeat/remote/filings/_filing_detail_303.py`, `src/aeat/remote/filings/_filing_detail_390.py` (per-modelo typed record shapes; concrete parsers deferred to Phase 2).
- Created: `src/aeat/remote/test_schema.py`, `src/aeat/remote/test_status.py`, `src/aeat/remote/test_protocols.py` (strict / frozen / extra-forbid / enum-exhaustiveness / Protocol-conformance coverage).
- Created: `src/aeat/remote/test_no_write_surface.py` + `src/aeat/remote/_no_write_surface_fixture.txt` (Layer 3 grep guard walking the full tree without whitelisting; forbidden tokens loaded from the sidecar fixture at runtime).

## Description

Every pydantic record uses `ConfigDict(strict=True, frozen=True,
extra="forbid")` and carries a `mode: Literal["read"] = "read"`
field. `CasillaDataType` is reused from `aeat.domain.schema` so remote
casillas type-check against the curated catalogue without fanning
out a duplicate enum. `AwareDatetime` is used for every timestamp
so tz-naive datetimes fail validation up-front. Monetary values in
the per-modelo detail records are typed `Decimal`.

`RemoteFilingStatus` closes the seven statuses the ADR enumerates
(`PRESENTADA`, `EN_TRAMITACION`, `RECHAZADA`, `SUBSANADA`,
`COMPLEMENTARIA`, `ANULADA`, `UNKNOWN`). The module ships a
`classify_status` helper that performs case-insensitive,
whitespace-tolerant, accent-sensitive matching against the known
Spanish strings. Unknown input folds into `UNKNOWN` and emits a
`logging.warning` through `aeat.core.logging.get_logger(__name__)` with
the raw string and optional modelo / period context.

`RemoteFilingFetcher` and `NotificationReader` are
`@runtime_checkable` Protocols that duck-type the existing
`StatusReader` surface but narrow the return type to the new
`aeat.remote` aggregates. Protocol tests use Protocol-conforming
Python classes declared inline; no mock-library imports appear
anywhere. Phase 2 adapters will realise the Protocols against the
live post-auth Playwright session without this subpackage ever
importing from `aeat.status._reader` internals.

Write-guard coverage is layered:

- Layer 1 (structural pydantic marker) - `mode: Literal["read"] = "read"` on every record; no `"write"` literal appears in any module under `src/aeat/remote/` (verified by the grep test, which composes the forbidden literal from fragments at runtime).
- Layer 2 (public API contract) - sealed `__all__` alphabetised and rejects write-verb prefixes (English + Spanish) via the grep test.
- Layer 3 (unit-test grep guard) - the walker test inspects every `.py` file under the subpackage, including itself. Forbidden tokens are loaded at runtime from the sidecar fixture so the test source never materialises them. No file is whitelisted and no `# noqa` hides a diagnostic.

Layers 4 and 5 are owned by Phase 2 (live paths and the
`requires_live_enabled()` gate); Phase 1 does not ship any live
surface.

The relative-imports mandate is respected throughout - every
cross-subpackage reference (`from ..schema import CasillaDataType`,
`from ..errors import AeatError`, `from ..logging import get_logger`)
is relative. No absolute `aeat.*` import appears in any new module
under the subpackage.

## Tests

- `just lint` - green (`ruff check .` plus the custom relative-imports check).
- `just typecheck` - green (`ty check src tests`).
- `uv run pytest -m unit src/aeat/remote/` - 38 passed.
- Repository-wide `uv run pytest` (default unit-only selector) -
  3126 passed, 5 skipped, 28 deselected. One pre-existing, unrelated
  failure in `tests/test_marker_integrity.py` against
  `src/aeat/adapters/outbound/aeat/export/_formats/_test_fixtures.py` that predates
  this branch and is out of Phase 1 scope (verified by stashing the
  working tree; failure persists on the unmodified branch tip).

No audit report has been generated yet for phase-1; the mandatory
`vaultspec-code-reviewer` audit runs next and will land under
`.vault/audit/` once the reviewer persona has inspected the phase-1
surface.
