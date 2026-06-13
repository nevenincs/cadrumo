---
tags:
  - '#research'
  - '#aeat-verify'
date: '2026-04-24'
modified: '2026-04-24'
related:
  - "[[2026-04-22-ruleset-architecture-adr]]"
  - "[[2026-04-21-calc-verification-adr]]"
---



# `aeat-verify` research: `remote-aeat-domain-and-reconciliation`

Research scope for issue #239: design the strict-pydantic, read-only model of
the authenticated AEAT sede electronica surface and the
`FilingDraft` to `RemoteFiling` reconciliation layer that surfaces the three
Kent-observable states `MATCH`, `DIVERGENT`, and `NOT_YET_FOUND`. The ADR
derived from this document must lock (a) the naming boundary (no collisions
with the existing local `aeat.application.verification` module), (b) the
`aeat.remote` subpackage shape, (c) the reconciliation vocabulary built on
top of `aeat.application.sync._divergence`, and (d) a five-layer write guard that makes
state mutation structurally unreachable.

## 1. Post-auth AEAT sede electronica navigation graph

### Known / canonical URL surfaces

The codebase already encodes the following post-auth paths. Values marked
`Settings` are overridable via `aeat.core.config.Settings`; constants inline in a
module are provisional (owned by the first feature that needed them).

| Surface | Path / template | Owner | Status |
| --- | --- | --- | --- |
| Auth-method selector | `/static_files/common/html/selector_acceso/SelectorAccesos.html?rep=S&ref={target}&aut=CP` | `Settings.aeat_clave_sede_access_url_template` | canonical, live-tested on 2026-04-21 |
| Mis expedientes (default post-auth target) | `/wlpl/TEWV-CORE/ResumenVlt` | `Settings.aeat_sede_expedientes_path` | canonical |
| Expedientes listing (parser) | `/wlpl/TC-UTIL/Expediente?COPT=Y` | `_EXPEDIENTES_PATH` in `src/aeat/status/_reader.py` | provisional, inline constant |
| Expediente detail page | `/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}` | `Settings.aeat_status_detail_url_template` | provisional, templated fallback - real URL usually comes from the parsed anchor |
| Mis notificaciones | `AEAT_STATUS_NOTIFICACIONES_PATH` (added by PR #312) | `Settings` | landing in PR #312 (open) |
| Justificante PDF URL | `Expediente.justificante_url` (parser-captured) | `src/aeat/status/_models.py` | captured live but not navigated by the reader - PDF parse is offline |
| Portal entries (pre-auth and mixed) | 44 entry modules under `src/aeat/domain/portals/_entries/` | `aeat.domain.portals` | rich metadata, but pre-auth / entry surfaces only |

### Post-auth surfaces the project has not yet modelled

`StatusReader` exposes six `fetch_*` methods of which only two are wired.
The remaining four are stubs that raise `StatusReaderError("surface not yet
implemented (#43 follow-up)")`:

- `fetch_devoluciones` - "Mis devoluciones" refund tracker.
- `fetch_borrador_irpf` - the pre-filled IRPF draft state.
- `fetch_datos_fiscales` - third-party payor data (employers, banks, pensions).
- `fetch_calendario` - personalised filing calendar.

Zero-coverage surfaces Kent cares about that are not even stubbed:

- Notification-centre (`Notificaciones Electronicas Obligatorias`, NEOs) and
  the `acuse de recibo` download dialog.
- Requerimientos inbox specifically (separate from ordinary notificaciones).
- Apoderamientos / representantes listing.
- Domiciliacion bancaria state (is SEPA direct debit set up for a filing?).
- `Consulta de pagos` - payments Kent has made or owes.
- Complementaria linkage - AEAT prints the parent `expediente_id` on the
  detail page; this is captured as `FiledModeloMetadata.complementaria_of`
  in `src/aeat/history/_models.py` but only for the three HTML parsers that
  exist today (130, 303, 390).

### Gaps issue 239 must fill

The reconciliation logic needs a canonical `RemoteFiling` record that
projects the AEAT-authoritative view of a single filing. Today this shape
exists only implicitly inside `FiledModelo` + `FiledModeloMetadata` in
`aeat.history._models`, which means:

- No typed modelo status enum - `status: str = Field(min_length=1, max_length=128)` is free-form Spanish prose as AEAT prints it (`"Presentada"`, `"En tramitacion"`, `"Rechazada"`).
- No rectifying-chain structure beyond a single `complementaria_of` pointer.
- No acuse / receipt abstraction - `justificante_url` is a bare URL.
- No "filing not found" shape - today a missing expediente is just an empty
  tuple return from `list_expedientes`, with no explicit "AEAT has no
  record of this period yet" record that the reconciler can persist.
- No cross-surface composition - notifications, devoluciones, acuses,
  borradores are each islands instead of being reachable through a single
  `RemoteFilingView` aggregate.

Issue 239 should introduce the `aeat.remote` subpackage whose `RemoteFiling`
record is the load-bearing aggregate of the post-auth surface, composed
from the already-typed `aeat.status` and `aeat.history` primitives plus the
new modelo-status enum and the new `FilingNotFound` record.

## 2. What `aeat.status` already provides vs. what is provisional

### Public API surface

`src/aeat/status/__init__.py` exports 26 symbols. Pydantic records:
`Expediente`, `Notificacion`, `Devolucion`, `BorradorIrpf`, `DatosFiscales`,
`Payor`, `CalendarioEntry`. Enums: `AeatStatusKind`, `PayorKind`. Errors:
`StatusReaderError`, `StatusAuthError`, `StatusParseError`,
`StatusNotFoundError`. Protocols: `BrowserSessionLike`,
`CertificateBackend`. Infrastructure: `StatusReader`, `StatusCache`, plus
the four `SiteHealth*` records and three parser functions from
`_site_health_parsers.py`. Every record is `strict=True, frozen=True,
extra="forbid"` via `_StatusRecord`'s `ConfigDict`.

### `StatusReader` method inventory

| Method | Status | Returns typed? | Notes |
| --- | --- | --- | --- |
| `fetch_expedientes` | wired, live-tested | `tuple[Expediente, ...]` | cache-aware, read-only, pagination TBD |
| `list_expedientes` | wired (wraps `fetch_expedientes`) | `tuple[Expediente, ...]` | conforms to `aeat.history.ExpedienteSource` Protocol |
| `fetch_detail_html` | wired | `tuple[str, AnyHttpUrl]` | raw HTML, read-only, conforms to `aeat.history.FilingDetailFetcher` Protocol |
| `fetch_filing_detail(modelo, period)` | wired but provisional | `tuple[FiledModelo, ...]` | composition facade over `aeat.history.HistoryFetcher`; only 130/303/390 parsers registered |
| `fetch_notificaciones` | stub becoming wired via PR #312 | `tuple[Notificacion, ...]` | parser ships in PR #312 |
| `fetch_devoluciones` | stub, raises | `tuple[Devolucion, ...]` | no parser |
| `fetch_borrador_irpf` | stub, raises | `BorradorIrpf or None` | no parser |
| `fetch_datos_fiscales` | stub, raises | `DatosFiscales` | no parser |
| `fetch_calendario` | stub, raises | `tuple[CalendarioEntry, ...]` | no parser |

### `fetch_filing_detail` - the load-bearing provisional method

Signature on `StatusReader`: `async def fetch_filing_detail(self, modelo:
str, period: str, *, use_cache: bool = True) -> tuple[FiledModelo, ...]`.
The composition is fully written but only three modelo parsers are
registered in `aeat.history._parsers` (130, 303, 390). Anything else
raises `HistoryUnsupportedModeloError` at fetch time.

Notable provisional details:

- Return type is `tuple[FiledModelo, ...]`, not an aggregate -
  reconciliation must iterate and dedupe when a period has a rectifying
  chain.
- `FiledModelo.calculations` is a `RawCalculationPayload` whose `casillas:
  dict[str, str]` is deliberately string-typed (casilla coercion is the
  consumer's job) - the reconciler has to resolve the `data_type` via
  `aeat.domain.casillas.CasillaRecord` before doing any numeric comparison.
- The `complementaria_of` field is captured only when the per-modelo HTML
  surface prints a parent reference; 390 is the annual summary and has no
  rectifying chain.
- `FiledModeloMetadata.status` is free-form Spanish. Issue 239 must introduce a
  closed `RemoteFilingStatus` enum with fallback to the raw string for
  values the enum has not yet seen.

### Read-only guard already in place

`src/aeat/status/test_no_write_surface.py` walks every `.py` file under
`src/aeat/status/` and asserts:

- No `page.fill`, `page.click`, `page.type`, `page.select_option`,
  `page.check`, `page.press`, `page.set_input_files`, `form.submit`, or
  bare `.click()` call exists anywhere in the tree.
- No symbol in `aeat.status.__all__` matches the write-verb regex
  `^(submit|send|ack|acknowledge|mark_|confirm|file_|post_)`.

This is the template issue 239 must replicate verbatim for `aeat.remote` and
`aeat.application.filing.reconciliation`, extended with the Spanish verb set.

## 3. `aeat.adapters.outbound.aeat.auth` surface consumed as-is

### Entry points for live authentication

The sanctioned Cl@ve-movil entry points exported from `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py`:

- `ClaveMovilAuthProvider` - the concrete provider that drives a headed
  Playwright session to the QR page, waits on AEAT's own JS polling, and
  returns an `AeatLoginAssertion` once the user has approved the push on
  his phone. Non-QR fallback (DNI/NIE + contraste) is controlled by
  `Settings.aeat_clave_prefer_non_qr`.
- `ClaveMovilApprovalTimeoutError` - raised when the user does not approve
  within `Settings.aeat_clave_movil_timeout_ms` (default 300 000 ms, AEAT's
  observed window is approximately 5 min).
- `ClaveMovilConfigurationError` - raised when a required Cl@ve setting is
  missing or malformed at provider-construction time.
- `AeatAuthenticator` - facade composing the certificate loader, browser
  session factory, and login-assertion flow. Holds an 18-minute idle TTL
  as a code-level constant (`AEAT_SESSION_IDLE_TTL`).
- `AeatSession` - frozen pydantic record: "what it means to have live
  AEAT access right now". Carries no secret material; safe to log and
  serialise into the submission audit trail.
- `AeatLoginAssertion` - frozen pydantic record: "what happened the last
  time we verified live access". Used to gate downstream reader construction.
- `BrowserSessionFactory`, `BrowserSessionLike`, `BrowserContextLike`,
  `BrowserPageLike`, `BrowserResponseLike` - Protocol seams so tests can
  provide real Protocol-conforming classes without importing Playwright at
  unit-test time.
- `AeatAccessGate` and `AeatGateEnvSnapshot` - the unified env-var
  precondition gate documented in section 8.

### Cl@ve-movil flow shape (what Kent sees)

- Fresh login: `ClaveMovilAuthProvider` opens a headed Playwright window
  and navigates to the Cl@ve selector page (`aeat_clave_sede_access_url_template`
  with `{target}` = the URL-encoded post-auth target, default
  `/wlpl/TEWV-CORE/ResumenVlt`).
- The page renders a QR code; Kent scans it with the Cl@ve app on his
  phone (or uses DNI/NIE + contraste via the non-QR fallback).
- The push notification appears on his phone; he taps "Aceptar". This
  is the 2FA step - the live test mandate for issue 239 forbids mocking,
  stubbing, or patching around it.
- AEAT's own JavaScript on the page polls its backend; when the approval
  lands the page navigates to the target. `ClaveMovilAuthProvider` waits
  on that navigation and returns an `AeatLoginAssertion`.
- Resume-from-storage-state (`aeat auth status` reports an active
  session): the provider opens headlessly because no human interaction
  is needed.
- Once the session is asserted, `AeatSession` carries: the provider kind,
  the sidecar path, the assertion timestamp, the idle-TTL deadline, and
  the auth-provider-specific detail record (`ClaveMovilSessionDetail`).

### Live-test env gates

`Settings` field: `aeat_live_tests_enabled: bool` - gates
`@pytest.mark.live_read` tests. The canonical env var is
`AEAT_LIVE_TESTS_ENABLED` (not `AEAT_LIVE_TESTS`). The helper
`aeat.entrypoints.cli._live.requires_live_enabled()` skips the calling test with a clear
message when the flag is false. `AeatGateEnvSnapshot` also captures two
sibling vars for the audit log: `AEAT_LIVE_SUBMIT_ENABLED` (write gate, must
remain false for issue 239) and `PYTEST_CURRENT_TEST` (presence-only signal that
pytest is running). Live tests under issue 239 must use this helper; no ad-hoc
`if os.environ[...]:` checks.

## 4. Naming-collision analysis and resolution

### Existing `Verification*` / `Verify*` / `Divergence*` symbols

Grep of `class (Verification|Verify|Reconcil|Divergence|Diff|Compare)[A-Z]\w*`
across `src/aeat/`:

| Symbol | Module | Purpose |
| --- | --- | --- |
| `VerificationStatus`, `VerificationVerdict`, `ClassifiedDiscrepancy`, `DiscrepancyCause`, `VerificationError`, `verify_declaracion` | `aeat.application.verification` | PDF-printed-value vs. formula-engine recomputation of an imported `DeclaracionFiling`. Entirely local - no remote touch. |
| `VerifyError` | `aeat.domain.casillas.errors` | Casilla-catalogue verifier error. |
| `VerifySeverity`, `VerifyFinding` | `aeat.application.setup._models` | Bootstrap doctor verifier records. |
| `VerificationIssue`, `VerificationReport` | `aeat.domain.financial.vat._schema` | VAT catalogue verifier output. |
| `VerificationIssue`, `VerificationReport` | `aeat.domain.normatives._schema` | Normative catalogue verifier output. |
| `VerificationIssue`, `VerificationReport` | `aeat.domain.manuals._verify` | Manual-rules verifier output. |
| `DivergenceClassification`, `DivergenceKind`, `DivergencePayload`, `DivergenceRecord`, `DivergenceClassifier`, 10 divergence payload variants | `aeat.application.sync` | Schema-level live-to-local divergence (corpus / ruleset / portal drift), not filing-instance divergence. |
| `DivergenceReviewItem` | `aeat.application.review._models` | Reviewer queue item referring to an existing divergence. |
| `DivergenceClassificationError`, `DivergenceRepositoryError`, `DivergenceRecordRepository` | `aeat.application.sync._errors`, `aeat.application.sync._repository` | Sync infrastructure. |
| `DivergenceSink` | `aeat.core.config` | Enum for sync-divergence sink (`FILE` / `STORAGE`). |
| `CompareOp` | `aeat.domain.schema._enums` | Comparison operator enum for schema constraints. |

### Existing CLI verbs

Grep of `@app.command` / `name="..."` across `src/aeat/entrypoints/cli/` for `verify`,
`reconcile`, `compare`, `diff`, `match`:

| Verb | Module | Purpose |
| --- | --- | --- |
| `aeat casillas verify` | `src/aeat/entrypoints/cli/casillas.py` | Validate canonical catalogue for a modelo / period. |
| `aeat submission verify` | `src/aeat/entrypoints/cli/submission/__init__.py` | Re-parse an exported fichero-BOE file and print its decoded headers + casillas. |
| `aeat submission diff` | `src/aeat/entrypoints/cli/submission/__init__.py` | Diff two fichero-BOE files and report byte + per-casilla deltas. |
| `aeat setup verify` | `src/aeat/entrypoints/cli/setup.py` | Run the verifier against a `SetupAnswers` JSON file. |
| `aeat justificante verify` | `src/aeat/entrypoints/cli/justificante/__init__.py` | Verify a justificante PDF. |
| `aeat vat verify` | `src/aeat/entrypoints/cli/vat.py` | Validate `VAT_CATALOGUE_2025` against the cross-record schema. |

No `reconcile`, `compare`, or `match` verbs exist today. `diff` is owned
exclusively by `aeat submission diff` (byte / file-level). `reconcile` is
open in both the Python namespace and the CLI namespace.

### Recommended naming resolution

Primary recommendation - the ADR should lock this:

- Remote surface subpackage: `aeat.remote`. Holds the `RemoteFiling`
  aggregate, `RemoteFilingStatus` enum, `RemoteNotification`,
  `RemoteAcuse`, `FilingNotFound` (explicit `NOT_YET_FOUND` signal),
  `RemoteFilingFetcher` Protocol, and the composition adapter that wraps
  `aeat.status.StatusReader` + `aeat.history.HistoryFetcher`. Every record
  carries the structural `mode: Literal["read"]` write-guard marker
  (section 8). This cleanly slots between `aeat.status` (raw AEAT
  primitives) and `aeat.application.filing` (local drafts).
- Reconciliation engine: `aeat.application.filing.reconciliation` (new submodule of
  `aeat.application.filing`). Exports `FilingReconciler`, `ReconciliationOutcome`
  (closed enum `MATCH | DIVERGENT | NOT_YET_FOUND`),
  `FilingReconciliationReport` (pydantic record: outcome + timestamp +
  divergence list), and `FilingDivergenceKind` (section 5). Sibling to
  `aeat.application.filing._import` which is the nearest-existing neighbour (also a
  local vs remote transform, in the opposite direction).
- CLI verb: `aeat filing reconcile <draft-path>` - no existing
  collision. Runs automatically as a stage inside `aeat sync run` once the
  dependencies land (see section 6 Protocol-stub strategy). The standalone
  CLI verb is the Kent-observable command; the sync integration is the
  "do not make Kent remember" surface.

Why not reuse `aeat.application.verification` for the new reconciler? The existing
`VerificationVerdict` record is already a published shape that Kent's UX
refers to as the "calc-verification" verdict (PDF vs engine). Overloading
`verify` to mean two different things (engine vs AEAT) would collapse two
orthogonal axes into one name and break the ADR-locked contract of
`aeat.application.verification`.

Alternative split 1 - `aeat.reconcile` top-level subpackage with both the
remote domain model and the reconciler inside it. Trade-off: keeps
reconciliation self-contained but pulls the remote-domain primitives out
of line with `aeat.status` / `aeat.history`, which are already the
"how we talk to AEAT" subpackages.

Alternative split 2 - keep the remote subpackage name `aeat.remote` but
put the reconciler in `aeat.application.sync._reconciliation`. Trade-off: `aeat.application.sync`
already owns schema-level divergence, and mixing filing-instance
divergence in there dilutes its invariant (ADDITIVE allowlist auto-heal is
safe only for schema-level additive changes, never for filing values).

Alternative split 3 - put everything under `aeat.verify.remote`.
Trade-off: creates a sibling of `aeat.application.verification` that reads the same
but means something different; high cognitive cost for future contributors.

## 5. Reusable divergence vocabulary from `aeat.application.sync`

### Inventory of `src/aeat/application/sync/_divergence.py`

Three enums and twelve pydantic records. The enums:

- `DivergenceClassification` = `ADDITIVE | BREAKING | BENIGN | SUSPICIOUS`.
- `DivergenceKind` = 10 closed variants covering schema-level drift.
- `ResolutionState` = `PENDING | AUTO_HEALED | HUMAN_APPROVED | REJECTED`.

Per-kind classification is a static `MappingProxyType` - deterministic,
not heuristic. `DivergenceKind` variants currently wired:

`CASILLA_ADDED_WITH_DEFAULT`, `LABEL_TRANSLATION_ADDED`,
`VIGENCIA_EXTENDED`, `CASILLA_REMOVED`, `CASILLA_TYPE_CHANGED`,
`FORMULA_CHANGED`, `LABEL_ES_CHANGED`, `PORTAL_URL_CHANGED`,
`FILING_STATUS_CHANGED`, `UNKNOWN_SHAPE`.

`DivergenceRecord` (frozen pydantic, `extra="forbid"`) fields:
`record_id: str(1..128)`, `detected_at: datetime`, `modelo:
ModeloIdentifier or None`, `classification: DivergenceClassification`,
`payload: DivergencePayload` (discriminated union), `resolution_state:
ResolutionState = PENDING`, `notes: str or None = None`.

### Schema-level vs filing-instance boundary

The existing vocabulary is schema-level: it describes drift in the
corpus, ruleset, portal, and the generic `FilingStatusChanged` "this
expediente's status string moved". It is not expressive enough for
filing-instance divergence because:

- There is no "casilla value mismatch" variant - only
  `CASILLA_TYPE_CHANGED`, which is about the type of a casilla in the
  schema, not the value in a specific filing.
- There is no "filing not yet found" variant - a schema-level consumer
  does not care about per-filing presence.
- The classification table is tuned for auto-heal safety (ADDITIVE
  implies heal), which is never safe for filing values.

### Proposed `FilingDivergenceKind` (for `aeat.application.filing.reconciliation`)

| Variant | Reconciliation outcome | Payload shape (proposed) |
| --- | --- | --- |
| `CASILLA_VALUE_MISMATCH` | `DIVERGENT` | `modelo, period, casilla_id, local_value, remote_value` (both as string after `data_type` coercion) |
| `CASILLA_MISSING_LOCAL` | `DIVERGENT` | `modelo, period, casilla_id, remote_value` - AEAT reports a casilla the local draft never set |
| `CASILLA_EXTRA_LOCAL` | `DIVERGENT` | `modelo, period, casilla_id, local_value` - local draft has a value AEAT does not |
| `FILING_STATUS_DIVERGENCE` | `DIVERGENT` | `modelo, period, expected_status, remote_status` - e.g. local says APPROVED but AEAT says `"Rechazada"` |
| `ROUNDING_ONLY` | `MATCH` (soft) | `modelo, period, casilla_id, local_value, remote_value, delta` - sub-tolerance delta |
| `FILING_NOT_YET_FOUND` | `NOT_YET_FOUND` | `modelo, period, expected_expediente_id`, `remote_expediente_ids_seen: tuple[str, ...]` - Kent-loud "did you actually upload it?" payload |

Mapping to the three Kent-observable terminal states:

- `MATCH` = zero entries or only `ROUNDING_ONLY` entries within tolerance.
- `DIVERGENT` = one or more of `CASILLA_VALUE_MISMATCH`,
  `CASILLA_MISSING_LOCAL`, `CASILLA_EXTRA_LOCAL`, `FILING_STATUS_DIVERGENCE`.
- `NOT_YET_FOUND` = the single `FILING_NOT_YET_FOUND` entry, mutually
  exclusive with any of the above (if AEAT has no record, casilla-level
  comparison is undefined).

Why not overload `sync.DivergenceKind`? Because its classification table is
a source of truth for auto-heal safety, and adding value-level kinds would
force every future reviewer of that table to reason about two orthogonal
axes. The static guarantee "ADDITIVE implies safe to heal" must remain
narrow. The correct move is to share the shape (frozen, discriminator on
`kind`, strict, `extra="forbid"`, `record_id` + `detected_at` shell)
while keeping the vocabulary isolated.

### Shape to reuse verbatim

- `model_config = ConfigDict(strict=True, frozen=True, extra="forbid")` on
  every payload member and the record shell.
- `Annotated[... | ... | ..., Field(discriminator="kind")]` discriminated
  union pattern.
- Static `MappingProxyType` classification table per-kind. For filing
  reconciliation, the "classification" maps kinds to outcomes
  (`MATCH | DIVERGENT | NOT_YET_FOUND`) rather than sync buckets.
- `ResolutionState` - reuse as-is; the reconciler persists records in
  `PENDING` and the reviewer CLI can promote to `HUMAN_APPROVED` /
  `REJECTED`. `AUTO_HEALED` does not apply (never auto-heal filing
  values).

## 6. Primary upstream: PR #312 (`feature/live-sync-engine`) territory

### PR #312 file footprint (26 files changed)

CLI: `src/aeat/entrypoints/cli/_live_reader.py`, `src/aeat/entrypoints/cli/filing/__init__.py` and
its test, `src/aeat/entrypoints/cli/inbox/_helpers.py`, `src/aeat/entrypoints/cli/inbox/fetch.py`
and its test, `src/aeat/entrypoints/cli/submission/test_help_text_contract.py`,
`src/aeat/entrypoints/cli/test_live_reader.py`.

Inbox: `src/aeat/inbox/__init__.py`, `src/aeat/inbox/_live_source.py`,
`src/aeat/inbox/test_live_source.py`.

Status: `src/aeat/status/__init__.py` (new notificacion parser export),
`src/aeat/status/_parsers/__init__.py`,
`src/aeat/status/_parsers/notificaciones.py` and its test,
`src/aeat/status/_reader.py` (wires `fetch_notificaciones`),
`src/aeat/status/test_reader.py`.

Config: `src/aeat/config.py` adds `AEAT_STATUS_NOTIFICACIONES_PATH`.

Vaultspec: live-sync-backend ADR / plan / research / audits land under
`.vault/`.

Fixtures: `tests/fixtures/aeat-pages/notificaciones/sample*.html`.

### Symbols issue 239 may import from PR #312 once it merges

- `StatusReader.fetch_notificaciones(*, since, use_cache) -> tuple[Notificacion, ...]`
  (replaces the stub in `src/aeat/status/_reader.py`).
- `LiveAeatNotificacionSource` in `src/aeat/inbox/_live_source.py` -
  structurally conforms to `aeat.inbox.NotificacionSource`, already
  declared at `src/aeat/inbox/_protocols.py`.
- `build_live_status_reader` async context manager in
  `src/aeat/entrypoints/cli/_live_reader.py` surfacing `LiveSessionUnavailableError`
  when no persisted auth sidecar exists.
- `import_filing_from_justificante` CLI path gains a
  `--from-aeat --modelo M --period P` variant that drives
  `StatusReader.fetch_filing_detail` - this is the closest-shaped
  precedent for `aeat filing reconcile` and issue 239 should mirror its gating
  and fallback semantics.

### Protocol-stub strategy while PR #312 is open

The reconciler needs two collaborators that PR #312 owns:

- A `RemoteFilingFetcher` surface that, given `(modelo, period)`, returns
  `tuple[FiledModelo, ...]` or a sentinel indicating "no matching
  expediente". This is effectively `StatusReader.fetch_filing_detail`.
- A `NotificationReader` surface that, given a filing, surfaces
  associated `Notificacion` records (acuse de recibo, requerimientos).
  This is effectively `StatusReader.fetch_notificaciones` filtered on
  the filing's expediente id or period.

`aeat.history._protocols` already declares `ExpedienteSource` and
`FilingDetailFetcher` (the low-level raw-HTML surface). Issue 239 should add a
new higher-level Protocol to `aeat.remote` - name proposal
`RemoteFilingFetcher` - that returns typed `RemoteFiling` records rather
than raw HTML. The real implementation wraps `StatusReader` +
`HistoryFetcher` but the Protocol lets issue 239's unit tests use a real
Protocol-conforming Python class (not `unittest.mock`) for every test.

For notifications, issue 239 declares `NotificationReader` as a Protocol in
`aeat.remote` whose signature matches the shape PR #312 ships. When
PR #312 merges the real implementation slots in via the existing
structural-conformance pattern. If PR #312 has not merged by the time issue 239
is ready, the reconciler still builds and unit-tests cleanly against the
Protocol; only the live tests gate on the real fetcher.

No cross-import of PR #312's private modules; Protocols live in
`aeat.remote._protocols` and duck-type on the public facade method names.

## 7. Seventeen-modelo filing-detail coverage

### Modelos shipped by the existing corpora

Ruleset modules under `src/aeat/domain/formulas/_rulesets/`:
`MODELO_100_SUMMARY_2025`, `MODELO_111_2024 / 2025`, `MODELO_115_2024 / 2025`,
`MODELO_123_2024 / 2025`, `MODELO_130_2024 / 2025`,
`MODELO_131_2024 / 2025`, `MODELO_180_2024 / 2025`, `MODELO_200_2024`,
`MODELO_202_2025`, `MODELO_303_2024 / 2025`, `MODELO_390_2025`. That is 17
rulesets across 14 modelos (plus 100-summary which is a derived annual
synthesis).

Declaracion extractors under `src/aeat/adapters/inbound/declaracion/_extractors/` (PDF to
`DeclaracionFiling`): 036, 037, 111, 115, 123, 130, 131, 180, 190, 193,
200, 202, 232, 303, 347, 349, 369, 390, 720, 840. Superset of the
rulesets - 190, 193, 232, 347, 349, 369, 720, 840, 036, 037 have PDF
extractors but no rulesets yet.

Submission export formats under `src/aeat/adapters/outbound/aeat/export/_formats/` (fichero
BOE generation): 130 (2024, 2025) and 303 (2024, 2024 preview, 2025).

History (AEAT-scraped `FiledModelo`) parsers under
`src/aeat/history/_parsers/`: 130, 303, 390.

### End-to-end readiness map

| Modelo | Ruleset | PDF extractor | Submission format | History parser | End-to-end reconcilable today? |
| --- | --- | --- | --- | --- | --- |
| 130 | 2024, 2025 | yes | 2024, 2025 | yes | yes (primary target) |
| 303 | 2024, 2025 | yes | 2024, 2025 | yes | yes (primary target) |
| 390 | 2025 | yes | no | yes | read-only reconciliation (no submission path) |
| 100 (IRPF annual) | 2025 summary | no (annual) | no | no | no - relies on borrador surface |
| 111 | 2024, 2025 | yes | no | no | ruleset + extraction only |
| 115 | 2024, 2025 | yes | no | no | ruleset + extraction only |
| 123 | 2024, 2025 | yes | no | no | ruleset + extraction only |
| 131 | 2024, 2025 | yes | no | no | ruleset + extraction only |
| 180 | 2024, 2025 | yes | no | no | ruleset + extraction only |
| 190 | no | yes | no | no | extraction only |
| 200 | 2024 | yes | no | no | ruleset + extraction only |
| 202 | 2025 | yes | no | no | ruleset + extraction only |
| 347, 349, 369, 720, 840, 036, 037, 193, 232 | no | yes (some) | no | no | extraction only / none |

### Kent's filing rhythm versus priority tiers

- Tier 1 - immediate reconciliation target (Kent's quarterly / annual
  VAT + direct-estimation IRPF rhythm): 130 (quarterly simplified IRPF
  prepayment), 303 (quarterly VAT), 390 (annual VAT summary). All three
  have full ruleset + extractor + history parser; 390 has no submission
  format because AEAT does not accept fichero BOE for the annual summary.
- Tier 2 - payroll / retention obligations (only if Kent employs or
  pays retained income): 111 (employee retentions), 115 (rental
  retentions), 123 (capital retentions), 180 (annual rental summary),
  190 (annual retentions summary). All have rulesets or extractors but
  no history parser; add to issue 239 as follow-up issues.
- Tier 3 - simplified direct-estimation alternative: 131 (quarterly,
  module regime). Similar gap to Tier 2.
- Tier 4 - informational / corporate: 347 (third-party operations),
  349 (EU intracommunity), 369 (OSS), 200 / 202 (corporate tax - not
  autonomo), 232 (related-party ops), 720 (foreign assets), 840
  (economic activities tax). Low priority for reconciliation; many have
  no numeric casilla surface worth reconciling (347 / 349 are itemised
  lists, not value-by-casilla).
- Tier 5 - annual IRPF (100): needs the `borrador_irpf` surface
  which is not yet modelled; depends on `fetch_borrador_irpf` landing.

Issue 239 should scope the first implementation to Tier 1 (130, 303, 390) -
this is the intersection of "Kent files it quarterly or annually" and
"history parser exists today". Tier 2 follows as issue 239's follow-up issues,
each gated on the corresponding history-parser PR.

## 8. Write-guard architecture

### Layer 1 - Structural pydantic marker

Every record in `aeat.remote` and `aeat.application.filing.reconciliation` whose data
originates from an AEAT-authenticated interaction carries a literal-typed
field `mode: Literal["read"] = "read"` on a frozen strict pydantic model.
No `"write"` literal exists in the issue 239 surface at all - not as a reserved
value, not in a comment, not in a test fixture. This makes the type-checker
a write-guard too: any future PR that tries to add a `"write"` literal will
force an explicit widening of the `Literal` that the code reviewer will see.

### Layer 2 - Public API contract

Every public function / method exported from `aeat.remote` and
`aeat.application.filing.reconciliation` satisfies two invariants:

- Return type is a frozen pydantic record or a tuple of frozen records;
  never a handle that supports a `.submit()` / `.send()` / `.commit()` /
  `.finalize()` call on AEAT state.
- Side-effect surface is documented: navigates via
  `page.goto(..., wait_until="domcontentloaded")` and reads
  `page.content()`. Exactly one Playwright navigation primitive is
  whitelisted - the same one already used by `StatusReader.fetch_detail_html`.
  No `click`, `fill`, `type`, `press`, `select_option`, `check`,
  `set_input_files`, `form.submit`.

This contract is asserted by Layer 3.

### Layer 3 - CI grep guard (two tests, no new workflow file)

Augment the existing `test_no_write_surface.py` pattern for the two new
subpackages. Add a unit test under
`src/aeat/remote/test_no_write_surface.py` and
`src/aeat/application/filing/reconciliation/test_no_write_surface.py` that walks every
`.py` file in its tree and asserts no match on the union pattern made of:

- `page\.(fill|click|type|select_option|check|press|set_input_files)`
- `form\.submit`
- `\.click\(\)`
- `\b(submit|enviar|presentar|firmar)\s*\(`
- `requests\.(post|put|patch|delete)`
- `session\.(post|put|patch|delete)`
- `urllib\.request\.Request\([^)]*method=` plus `(POST|PUT|PATCH|DELETE)`

plus an `__all__` check for the forbidden write-verb regex already in use
(`^(submit|send|ack|acknowledge|mark_|confirm|file_|post_)`) extended with
the Spanish verbs (`^(enviar|presentar|firmar|radicar|remitir)`).

No new `.github/workflows/*.yml` file. The existing `Test (unit)` step in
`.github/workflows/ci.yml` already runs `uv run pytest --junitxml=junit.xml`
on every PR across Ubuntu and Windows, which picks up these pytest files
automatically. The CI contract is: if the grep pattern matches any line in
the two subpackages, the unit suite fails and the PR is red. This is
stronger than a workflow-level grep because the tests also introspect
`__all__` exports symbolically.

Optional belt-and-braces: add a third unit test that imports the entire
`aeat.remote` public module, builds one instance of every record, and
asserts `instance.mode == "read"` via `hasattr` + equality. This is the
Layer 1 structural marker checked at runtime.

### Layer 4 - Charter #116 alignment

Existing write-safety charter artefacts grep-confirmed in the tree:

- `src/aeat/adapters/outbound/aeat/export/test_live_write_4factor_gate_documented.py` -
  codifies the four-factor gate for ANY live write.
- `src/aeat/adapters/outbound/aeat/export/test_safety_helpers.py` - tests around the
  `AeatLiveSubmit*` helpers.
- `src/aeat/adapters/outbound/aeat/export/_engine.py::_submit_with_transport` - the sole
  production call site that can write to AEAT.
- `Settings.aeat_live_submit_enabled`, `Settings.aeat_live_write_unsafe_bypass`,
  `Settings.aeat_live_write_unsafe_bypass_confirm` - the three env gates
  that all must be `True` / exact-phrase-match before any write may fire.
- `AeatLiveReadNotEnabledError` at `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` -
  exception raised when the live-read gate is not satisfied. Issue 239's
  reconciler must wrap its live path in `AeatAccessGate` and propagate
  this error shape rather than inventing a new one.
- `AeatGateEnvSnapshot` - the pydantic record that captures the three
  env vars for every audit-logged operation. Issue 239 should emit this
  snapshot into every reconciliation run record so the audit trail shows
  "live-write gate was OFF when the reconciler ran".

Issue 239 consumes these as-is; does not add new write-safety helpers because
the whole point is that the reconciler has no write path to gate in the
first place.

### Layer 5 - Test discipline

- Every live test in issue 239 uses `aeat.entrypoints.cli._live.requires_live_enabled()`
  at the top of the test body. No ad-hoc env checks, no
  `@pytest.mark.skipif(os.environ.get(...))`.
- Every live test is marked `@pytest.mark.live_read` (never
  `@pytest.mark.live_write`).
- Every live test triggers the real Cl@ve-movil 2FA prompt on first run
  (Kent approves on his phone). Subsequent runs within the 18-minute
  idle TTL resume from storage state and do not re-prompt. No mocks, no
  stubs, no patches around the 2FA step.
- Tests that need a scratch fixture (a known filed expediente for a known
  period) source it from the corpus under
  `tests/fixtures/pdf_corpus/l3_synthetic/_generators/` to avoid drawing
  on Kent's real filings; for live-against-AEAT runs, the test asks for
  the `(modelo, period)` tuple via env var and skips cleanly if unset.
- Env gate name: `AEAT_LIVE_TESTS_ENABLED` (not `AEAT_LIVE_TESTS`).
  Double-check every new test for this exact spelling; the project has
  been bitten by the shorter misspelling historically.

## Open questions for the ADR phase

- `RemoteFilingStatus` enum - should unknown AEAT status strings be
  carried through as a `RemoteFilingStatus.UNKNOWN` variant plus a
  `raw_status: str` sibling, or should they raise at parse time and
  surface as a `FILING_STATUS_DIVERGENCE` during reconciliation? Both are
  defensible; the ADR must pick one.
- `ROUNDING_ONLY` tolerance - reuse the `Decimal("0.01")` default from
  `aeat.application.verification` or source it from `Settings` under a new
  `aeat_reconciliation_rounding_tolerance` field? The former keeps the
  two verifiers aligned (and Kent sees one "rounding" definition across
  the CLI); the latter gives per-deployment tuning.
- Sync-run integration - does `aeat sync run` call the reconciler
  unconditionally (once per modelo + period the user has a draft for),
  or does it gate on draft status (`READY_TO_SUBMIT` or `APPROVED`)?
  Kent-pattern says "do not make me remember" which leans toward
  unconditional, but unconditional could blow out the live-read surface
  on every sync.
- `FilingNotFound` record persistence - does it live in the same
  divergence-record sink as other reconciliation records, or in a
  separate "Kent must take action" queue surfaced by a distinct CLI
  command (to make the Kent-loud pattern louder)?
- Cl@ve-movil session reuse - is one reconciliation run allowed to hit
  `fetch_filing_detail` for multiple `(modelo, period)` tuples inside the
  same `AeatSession`, or must each `(modelo, period)` re-authenticate?
  The 18-minute idle TTL suggests reuse is safe; confirm against the
  Cl@ve provider's live behaviour before the plan phase.
