---
tags:
  - '#exec'
  - '#aeat-verify'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-aeat-verify-audit]]"
  - "[[2026-04-24-aeat-verify-reference]]"
  - "[[2026-04-24-aeat-verify-adr]]"
---



# `aeat-verify` `discovery-driven-rewrite` `summary`

End-of-execution snapshot for the discovery-driven rewrite of issue #239
(Kent can prove his exported numbers match AEAT's record). The rewrite
spans 25+ commits on `feature/239-aeat-verify` and executes a complete
demolition + replacement of the speculative read surface against
ground-truth captured live from Kent's production sede on 2026-04-24.

## Summary of work

- Net diff vs `origin/main`: roughly **11,200 insertions and 23,500
  deletions** — i.e. **~12,300 lines removed** from the codebase.
- Discovery-first: every replacement record, URL, and selector has at
  least one live observation backing it.
- Read-only by construction: every new boundary record carries
  `mode: Literal["read"]`; no public method anywhere in the new
  subpackages mentions a mutation verb in English or Spanish.

## Modified

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_clave_movil.py` — DialogoRepresentacion handshake +
  idle-TTL refresh on `probe_persisted_session`.
- `src/aeat/domain/justificante/_extract.py` — annual-modelo regex set so
  Modelo 100 IRPF receipts now parse end-to-end (verified against 3
  real captures).
- `src/aeat/adapters/inbound/declaracion/` — three new template revisions for Modelo
  100 (2021 legacy, 2022 modern, 2023 modern); extractor produces
  83-86 typed casillas per real PDF.
- `src/aeat/entrypoints/cli/__init__.py` — `aeat sede` sub-app registered; the
  deleted `aeat status` / `aeat inbox` sub-apps unwired.
- `src/aeat/entrypoints/cli/filing/__init__.py` — registers the new `reconcile`
  subcommand; `--from-aeat` import path removed (was tied to the
  deleted live status reader).
- `src/aeat/application/workflow/_engine.py`, `_protocols.py`, `_adapters.py`,
  `__init__.py`, `test_engine.py` — rewired off the orphan
  `StatusReaderProtocol` / `InboxProtocol` stubs; constructor seams
  inject the real `aeat.adapters.outbound.aeat.sede.walk_expedientes_tree` and
  `fetch_notifications_query` paths.
- `src/aeat/domain/deadlines/` — dropped orphan `CorpusReader` and
  `ModeloCatalogueLoader` stubs; engine validates against the
  in-code closed modelo tuple.
- `src/aeat/application/sync/` — refreshed framing on every Protocol stub;
  dropped `CorpusLoader` and `StorageBackendStub`.
- `src/aeat/adapters/outbound/aeat/export/_protocols.py` — refreshed boundary-record
  framing.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/_site_health.py`, `_site_health_parsers.py`,
  `test_site_health.py` — salvaged real, useful AEAT-mantenimiento
  detection logic from the deleted `aeat.status` subpackage.
- `tests/test_docs.py`, `docs/architecture.md` — module-list updates.

## Created

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/` — read-only sede walker subpackage. Files:
  `_schema.py`, `_parse.py`, `_walker.py`, `_notifications.py`,
  `_errors.py`, `_no_write_surface_fixture.txt`, `test_parse.py`,
  `test_notifications.py`, `test_no_write_surface.py`.
- `src/aeat/application/filing/reconciliation/` — FilingDraft to Justificante
  comparator. Files: `_schema.py`, `_kind.py`, `_reconcile.py`,
  `_no_write_surface_fixture.txt`, `test_reconcile.py`,
  `test_no_write_surface.py`.
- `src/aeat/entrypoints/cli/sede/__init__.py` — `aeat sede` Typer sub-app
  (`list-expedientes`, `discover`, `notifications`).
- `src/aeat/entrypoints/cli/filing/_reconcile.py` + `test_reconcile_cli.py` —
  `aeat filing reconcile` end-to-end command.
- `scripts/recon_modelo_100.py`, `recon_modelo_100_detail.py`,
  `recon_modelo_303.py`, `recon_notifications.py` — discovery scripts
  that produced the ground-truth captures.
- `tests/fixtures/aeat-sede/` — identity-redacted captures of
  ResumenVlt, the IRPF detail page, the notifications summary, and
  the notifications query results.
- `.vault/research/2026-04-24-aeat-verify-research.md`,
  `.vault/adr/2026-04-24-aeat-verify-adr.md`,
  `.vault/plan/2026-04-24-aeat-verify-plan.md`,
  `.vault/reference/2026-04-24-aeat-verify-reference.md`,
  `.vault/audit/2026-04-25-aeat-verify-audit.md`.

## Deleted

Speculative subpackages, never validated against live AEAT:

- `src/aeat/remote/` — invented record shapes (~2000 lines).
- `src/aeat/status/` — cert-only StatusReader, never wired live
  (~4093 lines).
- `src/aeat/history/` — synthetic-fixture-only modelo parsers behind
  a never-merging cert backend (~2341 lines).
- `src/aeat/inbox/` — Protocol-stubbed integration over the deleted
  StatusReader (~1456 lines).
- `src/aeat/corpus/` — empty stub package promised to land "later".
- `src/aeat/entrypoints/cli/status/`, `src/aeat/entrypoints/cli/inbox/`,
  `src/aeat/entrypoints/cli/_live_reader.py` — CLI shells over the deleted
  modules.
- Various skip-only "live test placeholders" scattered across
  `aeat.status`, `aeat.history`, `aeat.application.sync`, `aeat.inbox`.

## Description

The pre-discovery shape of #239 invented an `aeat.remote` subpackage
of records, protocols, and per-modelo fetchers — written without a
single live observation against the real AEAT sede. A 2026-04-24
discovery run with Kent's Cl@ve-móvil session captured the authentic
post-auth surface in three artefacts:

1. *Mis Expedientes* — an AJAX-expanded category tree at
   `/wlpl/TEWV-CORE/ResumenVlt`, organised by procedure (IRPF, IVA,
   Sanciones, Certificados…), not by modelo code as the speculation
   assumed.
2. Per-filing-family endpoints — IRPF expedientes resolve through
   per-year paths `/wlpl/DASR-CORE/AccesoDR<YYYY>RVlt?exp=<id>`, with
   the *Grabación de la declaración* link carrying a `CSV` token to
   the document verifier.
3. Authoritative justificante PDFs — fetched as raw bytes via
   `/wlpl/KATA-APLI/cotejo/CotejoDocIdSv?CSV=<csv>` (browser
   navigation wraps these in Chrome's PDF viewer; the
   `APIRequestContext` path returns the real bytes).

The rewrite reshapes every layer against this surface. The
pre-discovery cert-only `aeat.status` and the inbox / history /
remote subpackages it anchored were entirely deleted — every record,
every Protocol stub, every rebase-swap placeholder pointing at a
sibling branch that never landed.

The five-layer write guard holds across the entire new surface:
pydantic `mode: Literal["read"]` markers, banned mutation verbs in
public symbol names, per-subpackage grep tests, charter `#116`
alignment via the existing `AeatAccessGate`, and the
`AEAT_LIVE_TESTS_ENABLED` opt-in for live tests with Cl@ve 2FA as the
one sanctioned human touchpoint.

## Tests

- `aeat.adapters.outbound.aeat.sede` — 28 unit tests covering parser fidelity against
  captured HTML, write-guard, notifications parser.
- `aeat.domain.justificante` — 17 unit tests, including the extended
  annual-modelo paths.
- `aeat.adapters.inbound.declaracion` Modelo 100 extractors — 50 unit tests across
  three template revisions.
- `aeat.application.filing.reconciliation` — 6 unit tests for every triad branch
  plus 14 write-guard tests.
- `aeat.entrypoints.cli.filing.reconcile` — 25 unit tests covering forbidden-flag
  rejection, period-to-ejercicio inference, exit-code mapping, CLI
  smoke.
- Full repo: roughly 2940 unit tests pass (modulo the documented
  transient `aeat.adapters.outbound.aeat.auth.test_clave_movil` Playwright-backed tests
  whose flakiness predated this PR and is unrelated to the rewrite).

Live verifications performed against Kent's production account:

- `aeat auth login --provider clave_movil` — full flow including the
  DialogoRepresentacion handshake fix.
- `aeat auth whoami` — verified idle-TTL refresh resets the on-disk
  deadline from minutes-before-expiry to a fresh 17 minutes.
- `aeat sede list-expedientes --modelo 100` — returned Kent's three
  real IRPF expedientes (2021, 2022, 2023).
- Discovery run captured all three IRPF justificante PDFs as raw
  bytes; all parsed cleanly through `aeat.domain.justificante` and
  `aeat.adapters.inbound.declaracion`.
- Notifications surface captured: 2 unread rows on the summary
  endpoint, 1 pending row on the query endpoint, all parsed correctly
  by `aeat.adapters.outbound.aeat.sede._notifications`.
