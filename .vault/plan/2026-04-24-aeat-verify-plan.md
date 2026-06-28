---
tags:
  - '#plan'
  - '#aeat-verify'
date: '2026-04-24'
modified: '2026-04-24'
related:
  - "[[2026-04-24-aeat-verify-adr]]"
  - "[[2026-04-24-aeat-verify-research]]"
---



# `aeat-verify` plan: `remote-aeat-domain-and-reconciliation`

This plan delivers issue #239 in a single mono-PR that (a) introduces the
read-only `aeat.remote` subpackage as the project's first typed model of
the authenticated AEAT sede electronica and (b) introduces the
`aeat.application.filing.reconciliation` comparator that walks a `FilingDraft` against
a `RemoteFiling` and emits the three Kent-observable terminal states the
ADR locks — `MATCH`, `DIVERGENT`, `NOT_YET_FOUND`. Every task traces to a
specific ADR decision: the naming split between `aeat.remote` and
`aeat.application.filing.reconciliation`; the `FilingDivergenceKind` fork that keeps
the `aeat.application.sync._divergence.DivergenceKind` auto-heal invariant narrow;
the Protocol-stub strategy that isolates this work from PR #312
internals; the Tier-1 modelo scope (130, 303, 390) anchored on existing
history parsers; the rounding tolerance shared with `aeat.application.verification`
at `Decimal("0.01")`; the `FilingDraftStatus.APPROVED` gate for the
`aeat sync run` integration; and — most loud-bearingly — the five-layer
write guard (structural pydantic marker, public-API contract,
grep-based unit test, charter #116 alignment, live-test discipline) that
makes state-changing AEAT interaction structurally unreachable from the
new surface. The plan respects the three non-negotiables: zero writes,
Cl@ve-movil 2FA as the sole sanctioned human touchpoint on live paths,
and strict pydantic v2 with `ConfigDict(strict=True, frozen=True, extra="forbid")`
on every boundary-crossing record. No mocks, stubs, patches, or
`@pytest.mark.skipif(os.environ.get(...))` tricks; every live test
routes through `requires_live_enabled()` and `@pytest.mark.live_read`.

## Proposed Changes

The ADR breaks into eight concrete deliverables. Each deliverable is
mapped to the subpackage it lives in, the files it creates, and the
write-guard layers it satisfies.

- **New subpackage `aeat.remote`.** Sealed public API exporting only
  the domain records and Protocols the ADR catalogues. Contains the
  `RemoteFiling`, `RemoteCasilla`, `RemoteExpediente`,
  `RemoteNotification`, `RemoteReceipt`, `RemoteNavigationGraph`,
  `RemoteFilingRef` records, the `RemoteFilingStatus` StrEnum with
  `UNKNOWN` fallback, the `RemoteFilingFetcher` and `NotificationReader`
  `typing.Protocol`s that duck-type `StatusReader.fetch_filing_detail`
  and `StatusReader.fetch_notificaciones`, a `RemoteFetchError`
  hierarchy, the per-modelo `FilingDetail130` / `FilingDetail303` /
  `FilingDetail390` detail records, the post-auth navigation catalogue,
  and the read-only Playwright fetchers per Tier-1 modelo. Every
  record carries `mode: Literal["read"] = "read"` (Layer 1). The
  subpackage is covered by `test_no_write_surface.py` (Layer 3).

- **New subpackage `aeat.application.filing.reconciliation`.** Sealed public API
  exporting `reconcile`, `ReconciliationReport`, `ReconciliationStatus`
  (alias for the terminal-triad enum used by the public surface),
  `CasillaDelta`, `FilingDivergenceKind`, and
  `RECONCILIATION_TOLERANCE`. Contains the comparator, the trilingual
  `Translatable` narrative builder (es / en / hu) mirroring
  `aeat.application.verification._verify._compose_narrative`, and the persistence
  adapter that funnels `DIVERGENT` / `NOT_YET_FOUND` reports into the
  existing `aeat.application.sync._divergence.DivergenceRecord` sink without
  extending `DivergenceKind`. Covered by its own
  `test_no_write_surface.py` (Layer 3).

- **New CLI verb `aeat filing reconcile`.** Lands as a sibling of
  `aeat filing import` inside `src/aeat/entrypoints/cli/filing/__init__.py`.
  Supports `aeat filing reconcile <draft-id>` and
  `aeat filing reconcile --last --modelo <M> --period <P>`. Forbidden
  flags (`--write`, `--submit`, `--enviar`, `--presentar`, `--firmar`)
  are rejected at parser-construction time so a typo cannot even
  reach the command body (Layer 2). `--dry-run` is a no-op alias for
  symmetry with sibling commands; `--json` enables machine-readable
  output. Exit codes follow the ADR table (0 = `MATCH`, 1 =
  `DIVERGENT`, 2 = `NOT_YET_FOUND`, 4 = live-access error).

- **`aeat sync run` auto-reconciliation.** The sync-run orchestrator
  in `src/aeat/entrypoints/cli/sync/run.py` gains a post-schema-sync stage that
  iterates over local `FilingDraft`s whose `status` is exactly
  `FilingDraftStatus.APPROVED` and invokes the reconciler for each
  `(modelo, period)`. One `AeatSession` is reused across the whole
  pass (the 18-minute `AEAT_SESSION_IDLE_TTL` covers it). Divergent
  and `NOT_YET_FOUND` results are surfaced in the sync-run summary
  with a warning-level log and a prominent marker in the human
  output.

- **Five-layer write guard, concrete file additions.** Layer 1 lives
  in every record under both new subpackages (`mode: Literal["read"]`).
  Layer 2 lives in the public-API docstrings and the parser
  declaration of the CLI (forbidden flags rejected at parser level).
  Layer 3 lives in `src/aeat/remote/test_no_write_surface.py` and
  `src/aeat/application/filing/reconciliation/test_no_write_surface.py`, each a
  file-walking grep guard. Layer 4 lives in the reconciler's live
  path that consumes `AeatAccessGate` / `AeatGateEnvSnapshot` as-is
  (no new write-safety helpers introduced) and propagates
  `AeatLiveReadNotEnabledError` rather than inventing a new error
  shape. Layer 5 lives in the single live test at
  `src/aeat/remote/test_fetch_live.py`, gated by
  `requires_live_enabled()` and marked `@pytest.mark.live_read`.

- **Test corpus.** Unit tests under each new module; a
  `test_no_write_surface.py` under each new subpackage; one live test
  in `aeat.remote` that round-trips one known filing from Kent's
  account through Cl@ve-movil 2FA. No mocks, no stubs, no patches;
  Protocol-conforming Python classes are used everywhere a
  collaborator is needed in unit tests.

- **Tier scope.** Tier 1 (130, 303, 390) ships in this PR; Tier 2
  (111, 115, 131, 180, 190, 100) and Tier 3 (347, 349, 123) are
  deferred per the ADR. The per-modelo fetchers under
  `src/aeat/remote/filings/` are declared only for Tier 1 to keep the
  diff reviewable.

- **Pipeline gates.** Every phase closes with `just lint`, `just
  typecheck`, `just test`, and `just hooks` green on Windows. No lint
  or typecheck skips, no `# type: ignore`, no `# noqa` unless strictly
  local-issue justified.

## Tasks


- **Phase 1 — Remote domain foundation (`aeat.remote`)**
  1. Create `src/aeat/remote/__init__.py` with a sealed public API.
     Export exactly: `RemoteFiling`, `RemoteCasilla`,
     `RemoteExpediente`, `RemoteNotification`, `RemoteReceipt`,
     `RemoteNavigationGraph`, `RemoteFilingRef`, `RemoteFilingStatus`,
     `RemoteFilingFetcher`, `NotificationReader`, `RemoteFetchError`,
     `RemoteParseError`, `RemoteNavigationError`, `FilingDetail130`,
     `FilingDetail303`, `FilingDetail390`. Populate `__all__` in
     alphabetical order. No `submit`, `send`, `commit`, `finalize`,
     `presentar`, `enviar`, `firmar`, `radicar`, or `remitir` in any
     exported name (Layer 2).
  1. Create `src/aeat/remote/_schema.py` with every domain record the
     ADR catalogues: `RemoteFiling` (fields per ADR: `modelo`,
     `period`, `expediente_id`, `status: RemoteFilingStatus`,
     `raw_status: str`, `submitted_at: datetime`,
     `casillas: tuple[RemoteCasilla, ...]`,
     `receipts: tuple[RemoteReceipt, ...]`,
     `complementaria_of: str | None`, `mode: Literal["read"]`);
     `RemoteCasilla` (`casilla_id`, `raw_value: str`,
     `data_type: CasillaDataType`, `coerced_value`,
     `mode: Literal["read"]`); `RemoteExpediente`;
     `RemoteNotification`; `RemoteReceipt`; `RemoteNavigationGraph`;
     `RemoteFilingRef`. Every record uses
     `ConfigDict(strict=True, frozen=True, extra="forbid")` and
     carries `mode: Literal["read"] = "read"`.
  1. Create `src/aeat/remote/_status.py` with `RemoteFilingStatus`
     StrEnum (`PRESENTADA`, `EN_TRAMITACION`, `RECHAZADA`,
     `SUBSANADA`, `COMPLEMENTARIA`, `ANULADA`, `UNKNOWN`). Include a
     docstring table mapping known Spanish status strings (`"Presentada"`,
     `"En tramitacion"`, `"En tramitación"`, `"Rechazada"`,
     `"Subsanada"`, `"Complementaria"`, `"Anulada"`) to enum members.
     Unknown strings map to `UNKNOWN` and the caller preserves the raw
     Spanish prose in `RemoteFiling.raw_status`. Emit a
     `logging.warning` through `aeat.core.logging.get_logger(__name__)` with
     modelo + period context when `UNKNOWN` is selected.
  1. Create `src/aeat/remote/_protocols.py` with `RemoteFilingFetcher`
     and `NotificationReader` `typing.Protocol`s. Signatures duck-type
     `StatusReader.fetch_filing_detail(modelo: str, period: str, *,
     use_cache: bool = True) -> tuple[FiledModelo, ...]` and
     `StatusReader.fetch_notificaciones(*, since, use_cache) ->
     tuple[Notificacion, ...]` respectively but return the typed
     `aeat.remote` aggregates rather than raw history tuples. Both are
     `@runtime_checkable` so `isinstance` checks stay cheap in unit
     tests. No import from `aeat.status._reader` — the Protocol is
     enough.
  1. Create `src/aeat/remote/_errors.py` with a minimal error hierarchy
     rooted at the existing `aeat.core.errors.AeatError`: `RemoteFetchError
     < AeatError`, `RemoteParseError < RemoteFetchError`,
     `RemoteNavigationError < RemoteFetchError`. Frozen dataclasses or
     `class ... (AeatError)` per the rest of the project convention.
  1. Create `src/aeat/remote/filings/__init__.py` and one
     `src/aeat/remote/filings/_filing_detail_130.py`,
     `src/aeat/remote/filings/_filing_detail_303.py`,
     `src/aeat/remote/filings/_filing_detail_390.py`. Each file
     declares a `FilingDetail130` / `FilingDetail303` /
     `FilingDetail390` pydantic record that wraps a `RemoteFiling` and
     projects the casilla-level fields already parseable by
     `aeat.history._parsers`. Record-shape declarations only in this
     step; concrete parsers land in Phase 2. `mode: Literal["read"]`
     on every record; `ConfigDict(strict=True, frozen=True,
     extra="forbid")`.
  1. Unit tests: `src/aeat/remote/test_schema.py`,
     `src/aeat/remote/test_status.py`,
     `src/aeat/remote/test_protocols.py`. Assert strict / frozen
     behaviour (mutating a field raises `ValidationError`), enum
     exhaustiveness (every member round-trips via `StrEnum(value)`),
     `UNKNOWN` fallback on an unknown Spanish string (plus the
     `logging.warning` captured via `caplog`), and `extra="forbid"`
     rejection (adding an unexpected field raises). Protocol tests use
     a real Protocol-conforming Python class (never
     `unittest.mock.Mock`).
  1. Write-guard Layer 3 test:
     `src/aeat/remote/test_no_write_surface.py`. Walk every `.py` file
     under `src/aeat/remote/` and assert no match for the union
     pattern of `page\.(fill|click|type|select_option|check|press|set_input_files)`,
     `form\.submit`, `\.click\(\)`,
     `\b(submit|enviar|presentar|firmar|radicar|remitir)\s*\(`,
     `requests\.(post|put|patch|delete)`,
     `session\.(post|put|patch|delete)`, and
     `urllib\.request\.Request\([^)]*method=` combined with
     `(POST|PUT|PATCH|DELETE)`. Additionally, import `aeat.remote` and
     assert no symbol in `__all__` matches
     `^(submit|send|ack|acknowledge|mark_|confirm|file_|post_|enviar|presentar|firmar|radicar|remitir)`.
     Also assert every record instance built via the record's
     `model_construct(mode="read")` satisfies `instance.mode == "read"`
     — the Layer 1 runtime check.

- **Phase 2 — Concrete navigation + parsing (read-only Playwright paths)**
  1. Create `src/aeat/remote/_navigation.py` that promotes the
     provisional URL constants inline in `src/aeat/status/_reader.py`
     into a typed `NavigationNode` frozen pydantic record and an
     immutable tuple catalogue of nodes. Each node carries
     `mode: Literal["read"]`. No `.click()` for state changes; the
     only Playwright primitive referenced is `page.goto(...,
     wait_until="domcontentloaded")` followed by `page.content()`, the
     same pattern already used by `StatusReader.fetch_detail_html`.
  1. Implement `src/aeat/remote/filings/_fetch_modelo_130.py`,
     `src/aeat/remote/filings/_fetch_modelo_303.py`,
     `src/aeat/remote/filings/_fetch_modelo_390.py`. Each exports a
     `fetch(session: AeatSession, period: FilingPeriod) ->
     FilingDetail130 | FilingDetail303 | FilingDetail390` function
     that consumes `StatusReader.fetch_filing_detail` at first and
     projects the result into the Phase-1 record. Richer
     casilla-mapping work is left for follow-on PRs; for Tier 1 the
     one-to-one projection is sufficient. Every fetcher imports
     `AeatSession` from `aeat.adapters.outbound.aeat.auth` as a Protocol seam so tests can
     inject a Protocol-conforming Python class.
  1. Unit tests per fetcher under `src/aeat/remote/filings/`:
     `test_fetch_modelo_130.py`, `test_fetch_modelo_303.py`,
     `test_fetch_modelo_390.py`. Each tests a captured HTML fixture
     under `tests/fixtures/aeat-pages/filing_detail_{modelo}/` (reuse
     the existing convention established by
     `tests/fixtures/aeat-pages/notificaciones/`). No live network; no
     mocks — the tests assemble a small Protocol-conforming
     `RemoteFilingFetcher` that returns pre-parsed tuples.
  1. Live test:
     `src/aeat/remote/test_fetch_live.py`. Exactly one live test per
     ADR Layer 5. Decorated with `@pytest.mark.live_read` and
     `@pytest.mark.live`. The test calls
     `aeat.entrypoints.cli._live.requires_live_enabled()` at the top of the test
     body (no `@pytest.mark.skipif(os.environ.get(...))`). It logs in
     via `ClaveMovilAuthProvider` (triggering Kent's phone prompt on
     fresh sessions; resuming from storage state within the 18-minute
     `AEAT_SESSION_IDLE_TTL` thereafter), fetches one known filing for
     a `(modelo, period)` pair sourced from env vars, asserts the
     resulting `FilingDetail303` round-trips through
     `model_validate(instance.model_dump())`, and cleans up its
     browser session on teardown. The test MUST NOT call any write
     path; `test_no_write_surface.py` continues to pass after this
     test file lands.
  1. Re-run `src/aeat/remote/test_no_write_surface.py` after every
     new file lands under `src/aeat/remote/` — the grep walker
     auto-picks up new files so no modification to the test itself is
     required.

- **Phase 3 — Reconciliation comparator (`aeat.application.filing.reconciliation`)**
  1. Create `src/aeat/application/filing/reconciliation/__init__.py` with a sealed
     public API. Export exactly: `reconcile`, `ReconciliationReport`,
     `ReconciliationStatus` (alias for the terminal-triad enum;
     members `MATCH`, `DIVERGENT`, `NOT_YET_FOUND`), `CasillaDelta`,
     `FilingDivergenceKind`, `RECONCILIATION_TOLERANCE`. Populate
     `__all__` alphabetically. No `submit`, `send`, etc. (Layer 2).
  1. Create `src/aeat/application/filing/reconciliation/_schema.py` with
     `ReconciliationReport` (fields per ADR: `status:
     Literal["match", "divergent", "not_yet_found"]`,
     `casilla_deltas: tuple[CasillaDelta, ...]`, `remote_ref:
     RemoteFilingRef | None`, `draft_ref: FilingDraftRef`,
     `reconciled_at: datetime`, `narrative: Translatable`);
     `CasillaDelta` (`casilla_id: str`, `kind: FilingDivergenceKind`,
     `local_value: str | None`, `remote_value: str | None`, `delta:
     Decimal | None`, `narrative: Translatable`); `FilingDraftRef`
     (lightweight reference: `draft_id`, `modelo`, `period`,
     `profile_tax_id`, `status: FilingDraftStatus`); and a static
     `MappingProxyType` binding each `FilingDivergenceKind` to the
     Kent-observable triad entry. All records use
     `ConfigDict(strict=True, frozen=True, extra="forbid")`.
  1. Create `src/aeat/application/filing/reconciliation/_kind.py` with
     `FilingDivergenceKind` StrEnum — six variants per ADR:
     `CASILLA_VALUE_MISMATCH`, `CASILLA_MISSING_LOCAL`,
     `CASILLA_EXTRA_LOCAL`, `FILING_STATUS_DIVERGENCE`,
     `ROUNDING_ONLY`, `FILING_NOT_YET_FOUND`. Include a module
     docstring explicitly calling out that this enum is disjoint from
     `aeat.application.sync._divergence.DivergenceKind` and explaining why (ADR
     rationale section paragraph on the fork).
  1. Create `src/aeat/application/filing/reconciliation/_tolerance.py` with a
     single public constant `RECONCILIATION_TOLERANCE =
     Decimal("0.01")`. Docstring explicitly ties it to
     `aeat.application.verification._verify._DEFAULT_TOLERANCE` so a future
     contributor who nudges one sees the other. No import of
     `aeat.application.verification` at runtime — values are duplicated
     deliberately to keep the module dependency graph clean; the tie
     is documentational.
  1. Create `src/aeat/application/filing/reconciliation/_reconcile.py` exporting
     `reconcile(draft: FilingDraft, remote: tuple[RemoteFiling, ...],
     *, tolerance: Decimal = RECONCILIATION_TOLERANCE, now:
     Callable[[], datetime] = _utcnow) -> ReconciliationReport`. Flow
     per ADR: empty `remote` emits a single `FILING_NOT_YET_FOUND`
     delta and returns `status="not_yet_found"` with `remote_ref=None`;
     multiple filings pick the latest-by-`submitted_at` as the
     comparison anchor; per-casilla walk classifies each casilla into
     one of the six `FilingDivergenceKind` variants (`ROUNDING_ONLY`
     when `abs(delta) <= tolerance`); `FILING_STATUS_DIVERGENCE` when
     `draft.status == APPROVED` but `remote.status !=
     RemoteFilingStatus.PRESENTADA` (and equivalents); outcome
     derivation via the static kind-to-outcome `MappingProxyType`. The
     function is pure and async-free; it takes already-fetched
     `remote` data rather than a `RemoteFilingFetcher` — fetcher
     invocation is the caller's job (Phase 4 and Phase 5 wrap it).
  1. Create `src/aeat/application/filing/reconciliation/_narrative.py` with a
     trilingual (es / en / hu) `Translatable` narrative builder
     mirroring the pattern in
     `src/aeat/application/verification/_verify.py::_compose_narrative`. One
     narrative per `FilingDivergenceKind` variant plus one aggregate
     narrative at the report level. All three languages are required
     for every string; no partial localisation.
  1. Create `src/aeat/application/filing/reconciliation/_persist.py` as the
     adapter that turns a `DIVERGENT` or `NOT_YET_FOUND`
     `ReconciliationReport` into a `DivergenceRecord` consumable by
     the existing `aeat.application.sync` sink. Do NOT extend
     `aeat.application.sync._divergence.DivergenceKind`; instead, define a new
     `FilingReconciliationPayload` pydantic record in
     `_persist.py` that satisfies the `DivergencePayload` protocol
     shape (same `ConfigDict(strict=True, frozen=True,
     extra="forbid")`, same discriminator-on-`kind` pattern) without
     touching `aeat.application.sync` internals. Inspect
     `src/aeat/application/sync/_divergence.py` during implementation to confirm
     the payload surface accepts external variants via the
     discriminated union; if it does not, the payload is persisted as
     a wrapping record that satisfies the `DivergenceRecord.payload`
     type without cross-enum pollution (the ADR rationale paragraph
     on the fork governs this decision).
  1. Unit tests per file under `src/aeat/application/filing/reconciliation/`:
     `test_schema.py`, `test_kind.py`, `test_tolerance.py`,
     `test_reconcile.py`, `test_narrative.py`, `test_persist.py`.
     `test_reconcile.py` covers the triad × six `FilingDivergenceKind`
     variants × rounding edge cases (exact-on-tolerance, one-cent-over,
     one-cent-under, negative delta, zero-on-both-sides). Every
     collaborator is a Protocol-conforming Python class; no
     `unittest.mock`. `test_narrative.py` asserts every variant
     produces non-empty es / en / hu strings.
  1. Write-guard Layer 3 test:
     `src/aeat/application/filing/reconciliation/test_no_write_surface.py`. Same
     grep walker + `__all__` check + `mode == "read"` runtime check as
     Phase 1.8, retargeted at the reconciliation subpackage.

- **Phase 4 — CLI surface (`aeat filing reconcile`)**
  1. Add the `reconcile` subcommand inside
     `src/aeat/entrypoints/cli/filing/__init__.py` as a sibling of the existing
     `import` (registered as `import_`). Declared via the same
     `@app.command(...)` pattern used by sibling commands. Parameters:
     `draft_id: Annotated[str | None, typer.Argument(...)] = None`,
     `modelo: Annotated[str | None, typer.Option("--modelo", ...)] =
     None`, `period: Annotated[str | None, typer.Option("--period",
     ...)] = None`, `last: Annotated[bool, typer.Option("--last",
     ...)] = False`, `as_json: Annotated[bool, typer.Option("--json",
     ...)] = False`, `dry_run: Annotated[bool, typer.Option("--dry-run",
     ...)] = False` (no-op alias). The parser refuses `--write`,
     `--submit`, `--enviar`, `--presentar`, `--firmar` at declaration
     time — these flags are not defined, so Typer rejects them with
     its standard unknown-flag error; additionally, a module-level
     registration test asserts none of those flags appear in the
     parsed `Click` command's param list.
  1. Machine-readable JSON output via `--json` renders the
     `ReconciliationReport` via `report.model_dump_json(indent=2)`.
     Human-readable output follows the `aeat justificante verify`
     precedent — single-word status at top, bulleted casilla deltas,
     narrative tail.
  1. `--dry-run` is a no-op alias. The command is read-only by
     construction; the flag exists only for symmetry with sibling
     filing commands and is explicitly documented in the help text as
     such.
  1. Exit codes: `0` = `MATCH`, `1` = `DIVERGENT`, `2` = `NOT_YET_FOUND`,
     `4` = live-access error (raised as
     `AeatLiveReadNotEnabledError` from the live fetch path). The
     command maps these through `typer.Exit(code=...)`.
  1. Unit tests: `src/aeat/entrypoints/cli/filing/test_reconcile.py`. Cover
     success (`MATCH`), `DIVERGENT` output formatting,
     `NOT_YET_FOUND` formatting, `--json` round-trip through
     `ReconciliationReport.model_validate_json`, parser refusal of
     forbidden flags (`--write`, `--submit`, `--enviar`,
     `--presentar`, `--firmar` — each tested individually against
     Typer's runner), and exit-code mapping. Use `typer.testing.CliRunner`
     per the existing test conventions.

- **Phase 5 — Sync-run integration**
  1. Read `src/aeat/entrypoints/cli/sync/run.py` end-to-end first to locate the
     correct insertion point for the reconciliation stage (after
     schema-level divergence processing, before summary rendering).
     Wire the new stage as a dedicated async helper in a new
     `src/aeat/entrypoints/cli/sync/_reconcile_stage.py` that takes the existing
     sync-run context plus an
     `AsyncIterable[FilingDraft]` and emits an iterable of
     `ReconciliationReport`s. Gate entry on `draft.status ==
     FilingDraftStatus.APPROVED` only; skip drafts in every other
     state with a debug-level log.
  1. Within one `aeat sync run` invocation, reuse one `AeatSession`
     across all `(modelo, period)` reconciliations. Construct the
     session at the top of the stage via `AeatAuthenticator`; reuse
     the existing context-manager shape documented on
     `StatusReader`. Do not add new session-lifecycle primitives.
     The 18-minute `AEAT_SESSION_IDLE_TTL` covers a multi-modelo
     pass; TTL expiry during a run falls back to the existing
     re-auth path in `AeatAuthenticator`.
  1. Surface `NOT_YET_FOUND` prominently in the sync-run summary with
     a warning-level log through `aeat.core.logging.get_logger(__name__)`
     and an obvious marker in the human output (leading icon or
     upper-case label — follow the existing convention already used
     by schema-level divergence surfaces). `DIVERGENT` results feed
     the same summary block; `MATCH` results are logged at debug
     level only to keep the summary readable.
  1. Persist `DIVERGENT` and `NOT_YET_FOUND` reports into the
     existing `DivergenceRecord` sink via the Phase-3
     `_persist.py` adapter. One Kent-facing queue handles both
     schema-level and filing-level divergences per the ADR.
  1. Unit tests:
     `src/aeat/entrypoints/cli/sync/test_reconcile_stage.py`. Cover
     `FilingDraftStatus.APPROVED` gating (every other status is
     skipped), session reuse across multiple `(modelo, period)`
     pairs (a Protocol-conforming session wrapper counts
     invocations), summary formatting for mixed
     `MATCH`/`DIVERGENT`/`NOT_YET_FOUND` batches, and
     `DivergenceRecord` emission (via the `_persist.py` adapter).

- **Phase 6 — Pipeline gates**
  1. Run `just lint` until clean — no `# noqa` unless strictly
     justified by a local-to-a-file shape; no lint skips; no
     wildcard exclusions.
  1. Run `just typecheck` until clean — no `# type: ignore` without
     a targeted error code; no new entries in any
     `mypy.overrides` / `pyright.exclude` block; no widening of
     existing type-checker strictness settings.
  1. Run `just test` until green on Windows. Every new test is a
     regular (non-live) unit test except the single Phase 2.4 live
     test, which is skipped in CI by default via the
     `AEAT_LIVE_TESTS_ENABLED` gate.
  1. Run `just hooks` until clean. Any pre-commit hook failure
     drives a new commit, never `--no-verify`.
  1. If any new test marker (`live_read`) is not already registered
     in `pyproject.toml` / `conftest.py`, register it there; do not
     introduce a new marker namespace without a one-line docstring
     in the registration.
  1. Update the Kent-observable capability matrix under
     `docs/coverage/*.md` only if that directory already exists and
     already tracks reconciliation-adjacent surfaces; otherwise skip
     this step to avoid inventing documentation scaffolding this PR
     does not already maintain.

## Parallelization

A single implementing agent cannot truly parallelise across phases
because the git working tree is shared and file-level contention is
inevitable. The dependency graph does, however, admit concurrent
sub-agent dispatch in a handful of independent slices — worth naming
explicitly so the execute-phase orchestrator can pack work sensibly.

Phase 1 and the record-shape slice of Phase 3 (steps 3.1 – 3.4) are
genuinely independent — `aeat.remote._schema.py` and
`aeat.application.filing.reconciliation._schema.py` touch different subpackages,
import from different upstreams, and are covered by disjoint test
files. These two slices can be dispatched to parallel sub-agents
with no merge conflicts expected. Phase 1.7 and Phase 3.8 (the unit
test batches) likewise parallelise cleanly against each other.

Phase 2 depends strictly on Phase 1.6 (the per-modelo record
declarations must exist before the fetchers can import them). Within
Phase 2, the three per-modelo fetcher files (`_fetch_modelo_130.py`,
`_fetch_modelo_303.py`, `_fetch_modelo_390.py`) are pairwise
independent and can parallelise; so can their unit tests.

Phase 4 depends on Phase 3 (the CLI consumes the `reconcile` function
and the `ReconciliationReport` record). The CLI steps themselves
(4.1 through 4.5) are serial within the same file
(`src/aeat/entrypoints/cli/filing/__init__.py`).

Phase 5 depends on Phase 4 (sync-run calls the same comparator the
CLI calls) and on Phase 1 / 2 / 3 being green as a whole.

Phase 6 is strictly serial and terminal.

The write-guard grep tests (Phase 1.8 and Phase 3.9) can be written
in parallel with their subpackages — they auto-discover any file that
lands after them.

## Verification

### Plan Self-Review

- Every ADR decision covered by at least one task: the naming split
  (Phase 1.1 and 3.1 sealed-API exports), the `aeat.remote`
  subpackage shape with every catalogued record (Phase 1.1 – 1.6),
  the `RemoteFilingStatus` closed enum with `UNKNOWN` fallback
  (Phase 1.3), the Protocol-stub strategy for PR #312 (Phase 1.4),
  the `FilingDivergenceKind` fork disjoint from `DivergenceKind`
  (Phase 3.3 and 3.7), the `ReconciliationOutcome` / terminal triad
  mapping via static `MappingProxyType` (Phase 3.2 and 3.5), the
  per-casilla walk with rounding tolerance (Phase 3.5), the
  trilingual `Translatable` narrative (Phase 3.6), the
  `DivergenceRecord` sink reuse without enum extension (Phase 3.7),
  the CLI verb `aeat filing reconcile` as a sibling of `aeat filing
  import` (Phase 4.1 – 4.5), the `aeat sync run` gate on
  `FilingDraftStatus.APPROVED` (Phase 5.1), session reuse inside one
  sync run (Phase 5.2), and the Tier-1 scope (130, 303, 390 in
  Phase 1.6 and Phase 2.2).

- Every task names at least one concrete file path. Every step lists
  the file it creates or edits in inline backticks; no prose-only
  "something in aeat.remote" instructions. The grep tests
  (Phase 1.8 and 3.9) name the file they live in even though they
  walk their whole subpackage dynamically.

- The five-layer write guard appears across at least five distinct
  phases: Layer 1 (structural pydantic marker) is set in every
  record created in Phase 1.2, Phase 1.6, and Phase 3.2; Layer 2
  (public API contract) is enforced in Phase 1.1, Phase 3.1, and
  Phase 4.1; Layer 3 (grep unit test) lives in Phase 1.8 and
  Phase 3.9; Layer 4 (charter #116 alignment via
  `AeatAccessGate` / `AeatGateEnvSnapshot` /
  `AeatLiveReadNotEnabledError` propagation) is enforced in the
  live fetch path introduced in Phase 2.4 and in the sync-run
  stage of Phase 5.1; Layer 5 (live-test discipline —
  `requires_live_enabled()`, `@pytest.mark.live_read`, real
  Cl@ve-movil 2FA) is enforced in Phase 2.4. Five layers across
  five phases minimum.

- No phase imports from PR #312 internals. Phase 1.4 declares the
  `RemoteFilingFetcher` and `NotificationReader` Protocols; Phase 2
  fetchers import only from `aeat.adapters.outbound.aeat.auth` (the sanctioned public
  API) and from the Protocol declarations. No `from aeat.status._parsers
  import ...`, no `from aeat.inbox._live_source import ...`, no
  `from aeat.entrypoints.cli._live_reader import ...`.

- No phase touches `aeat.application.verification` internals (the
  `RECONCILIATION_TOLERANCE` constant in Phase 3.4 duplicates the
  value rather than importing from
  `aeat.application.verification._verify._DEFAULT_TOLERANCE`). No phase touches
  `aeat.adapters.outbound.aeat.auth` internals (only `AeatSession`, `AeatAccessGate`,
  `AeatGateEnvSnapshot`, `AeatLiveReadNotEnabledError`,
  `ClaveMovilAuthProvider`, `AeatAuthenticator` — all already public
  via `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py`). No phase touches
  `aeat.application.sync._divergence` enums — Phase 3.7 adds a new payload
  record inside `aeat.application.filing.reconciliation._persist` that satisfies
  the sink's existing Protocol shape; `DivergenceKind` is not
  widened. No phase touches `aeat.application.filing` approval state (Phase 5.1
  consumes `FilingDraftStatus.APPROVED` read-only; the draft
  lifecycle machinery in `src/aeat/application/filing/_review.py` is not
  modified).

- Clave 2FA live-test path exists and is gated correctly. Phase 2.4
  is the single live test, marked `@pytest.mark.live_read` and
  `@pytest.mark.live`, gated via `requires_live_enabled()` at the
  top of the test body. Real Cl@ve-movil push on first run (Kent
  approves); resume from storage state within the 18-minute
  `AEAT_SESSION_IDLE_TTL`. No mocks, no stubs, no patches around
  the 2FA step. Env var is `AEAT_LIVE_TESTS_ENABLED` (not
  `AEAT_LIVE_TESTS`).

- The CLI refuses every forbidden flag at parser level, not just
  runtime. Phase 4.1 does not define `--write`, `--submit`,
  `--enviar`, `--presentar`, or `--firmar` as Typer options —
  passing any of them to the command surfaces Typer's standard
  unknown-flag error before the command body runs. Phase 4.5 tests
  this behaviour individually for each flag.

- `Translatable` narratives cover es / en / hu. Phase 3.6 builds
  one narrative per `FilingDivergenceKind` variant plus one
  aggregate narrative; Phase 3.8 asserts every variant produces
  non-empty strings for all three languages.

- Pydantic v2 strict / frozen / `extra="forbid"` across every
  record. Every step that creates a record explicitly reiterates
  `ConfigDict(strict=True, frozen=True, extra="forbid")` so an
  executing agent cannot drop the invariant by accident.

- `just lint && just typecheck && just test && just hooks` is
  explicitly the last gate. Phase 6 steps 6.1 through 6.4 enumerate
  each recipe in order; no phase closes without running them.

### Plan Self-Review verdict

PASS. Every checklist item above resolves to a concrete step in the
Tasks section.

### Kent-observable acceptance matrix

- **MATCH** — Kent runs `aeat filing reconcile <draft-id>` 30
  minutes after uploading a Modelo 303 whose casillas match AEAT
  byte-for-byte. Exit code `0`. Output header reads `MATCH`. No
  bulleted deltas. Narrative tail states the reconciliation
  succeeded (es / en / hu). Unit test: `test_reconcile.py::test_match_zero_deltas`
  plus `test_reconcile.py::test_rounding_only_classifies_as_match`.

- **DIVERGENT** — Kent uploads a Modelo 303 with a one-euro error on
  casilla 46 and reconciles. Exit code `1`. Output header reads
  `DIVERGENT`. One bulleted delta for casilla 46 naming
  `local_value`, `remote_value`, and `delta`. Narrative tail
  identifies the casilla. Unit test:
  `test_reconcile.py::test_value_mismatch_outside_tolerance`.

- **NOT_YET_FOUND** — Kent runs reconcile 5 minutes after uploading
  (AEAT has not ingested yet). Exit code `2`. Output header reads
  `NOT_YET_FOUND`. No casilla deltas (the triad is mutually
  exclusive). Warning-level narrative tail asking "has AEAT actually
  received this filing?" in es / en / hu. Unit test:
  `test_reconcile.py::test_empty_remote_emits_not_yet_found`.

### Be-honest caveats (tests can be cheated)

Unit tests alone cannot prove the following, and no amount of
CI-green buys confidence here without a real live run:

- The real Cl@ve-movil 2FA flow end-to-end. The only live test
  (Phase 2.4) triggers a real push notification, but we cannot
  commit evidence of Kent's phone tap to the repo; the green test
  on Kent's workstation is the only signal.

- The real 18-minute idle TTL behaviour on the Cl@ve provider side.
  The `AEAT_SESSION_IDLE_TTL` constant is a code-level assumption;
  AEAT may expire sessions earlier or later in production, and
  the reconciliation session-reuse path (Phase 5.2) assumes the
  constant is accurate. First live `aeat sync run` invocation
  with more than one Tier-1 modelo is the ground truth.

- The real post-auth navigation catalogue. Phase 2.1 promotes the
  provisional URL constants from `src/aeat/status/_reader.py` but
  AEAT has been known to change URL templates without notice; the
  live test is the first signal that the catalogue is still
  accurate on the day the PR lands.

- AEAT status-string stability. `RemoteFilingStatus.UNKNOWN`
  fallback is the pressure-release valve (Phase 1.3), but until a
  live fetch exercises it against a filing whose status has just
  changed, the warning-log path is untested against reality.

- Rounding behaviour on AEAT's side for casillas at the
  sub-tolerance boundary. Unit tests cover the reconciler's
  side of the `Decimal("0.01")` boundary, but AEAT's own rounding
  has been observed to behave inconsistently across modelos in
  the past (research section 7 corollary); only live runs across
  Tier-1 modelos reveal whether `ROUNDING_ONLY` absorbs the
  day-one noise without spurious `DIVERGENT` classifications.

- The write-guard grep test is necessary but not sufficient. A
  future contributor who renames a write primitive in a language
  not covered by the grep union (e.g. a new Spanish verb, or a new
  Playwright method name introduced by a library upgrade) can
  slip past the guard. Layer 2 (code review) and Layer 4
  (charter #116) are the human backstops; the grep alone is not
  the whole safety net.

After Phase 6 closes, the project gets one typed read-only model of
the post-auth AEAT surface, one comparator that surfaces the three
Kent-observable states loudly, and a write-guard posture that makes
a write-path a compile-time + code-review + CI + charter + test
failure — not merely a runtime one.
