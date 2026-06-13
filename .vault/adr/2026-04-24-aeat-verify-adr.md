---
tags:
  - '#adr'
  - '#aeat-verify'
date: '2026-04-24'
modified: '2026-04-24'
related:
  - "[[2026-04-24-aeat-verify-research]]"
  - "[[2026-04-21-calc-verification-adr]]"
  - "[[2026-04-22-ruleset-architecture-adr]]"
---



# `aeat-verify` adr: `remote-aeat-domain-and-filing-reconciliation` | (**status:** `accepted`)

## Problem Statement

Issue #239 sits at the intersection of two distinct architectural gaps that
the project has carried since the post-auth AEAT surface first shipped.

The first gap is ontological. The authenticated AEAT sede electronica is a
rich and evolving domain — expedientes, filings, acuses, notifications,
requerimientos, domiciliaciones, payments, apoderamientos, borradores,
devoluciones, calendario — but no single subpackage owns a typed,
strictly-pydantic model of that domain. `aeat.status` exposes raw primitives
(`Expediente`, `Notificacion`, `Devolucion`, `BorradorIrpf`, `DatosFiscales`,
`Payor`, `CalendarioEntry`) with four `fetch_*` methods still stubbed out;
`aeat.history` owns the per-modelo parse of filed casillas; `aeat.domain.portals`
catalogues pre-auth entries. None of these aggregates the AEAT-authoritative
view of a single filing — the shape a reconciler needs to say "this is what
AEAT has on record for Kent's Q1 2026 Modelo 303". The closest-shaped record
today, `FiledModelo` + `FiledModeloMetadata`, is untyped at the status
boundary (`status: str` of free-form Spanish prose), has no explicit
"not-yet-found" variant, carries receipts only as bare URLs, and has no
cross-surface composition with notifications or acuses.

The second gap is functional. Kent needs to prove — in a Kent-observable,
machine-auditable way — that the numbers he just uploaded to AEAT match what
AEAT has on record. The `aeat.application.verification` module added in PR #301 verifies
that his imported `DeclaracionFiling` agrees with the formula engine's
re-computation of the same casillas; that is a local-only verdict. There is
no bridge from his local `FilingDraft` to AEAT's authoritative record, and
therefore no way to close the loop on "I filed it, AEAT received it, the
numbers line up". The post-fiasco rhythm of a Spanish autonomo — file, wait,
discover a rejection three weeks later inside an unread notification —
demands that the system surface divergence loudly and early, in exactly the
three states Kent will act on: `MATCH`, `DIVERGENT`, `NOT_YET_FOUND`.

Both gaps must be closed with a read-only, strictly-typed architectural
surface that cannot structurally produce a state-changing AEAT interaction.
AEAT has no sandbox; every write is legally binding against Kent's tax
identity, and the live-write safety charter (issue #116) forbids inventing
new write paths outside the single audited submission engine.

## Considerations

- `aeat.application.verification` already publishes a verdict surface — `VerificationStatus`,
  `VerificationVerdict`, `ClassifiedDiscrepancy`, `DiscrepancyCause`,
  `verify_declaracion` — and the CLI verb `aeat justificante verify`,
  `aeat casillas verify`, `aeat setup verify`, `aeat submission verify`,
  `aeat vat verify`. The word `verify` is already load-bearing in the
  Kent-facing vocabulary as "local PDF-vs-formula check". Overloading it
  for the AEAT-vs-local axis would collapse two orthogonal comparisons
  into one name.
- The 17-modelo corpus already ships, but filing-detail parsers (the
  HTML-to-`FiledModelo` surface under `aeat.history._parsers`) exist only
  for Modelos 130, 303, and 390. Every other modelo raises
  `HistoryUnsupportedModeloError` at fetch time today.
- `aeat.application.sync._divergence` owns a mature schema-level divergence vocabulary:
  `DivergenceClassification`, `DivergenceKind` (10 closed variants tuned
  for corpus / ruleset / portal drift), `ResolutionState`,
  `DivergenceRecord`. Its classification table is a statically-enforced
  auto-heal-safety contract — `ADDITIVE` implies safe-to-heal, a guarantee
  that must stay narrow. Filing-instance value divergence is a different
  axis and does not belong in that table.
- Issue #312 (`feature/live-sync-engine`) is in flight and touches 26
  files overlapping the post-auth surface: it wires
  `StatusReader.fetch_notificaciones`, adds `LiveAeatNotificacionSource`,
  and ships the `build_live_status_reader` async context manager.
  Issue #239 must not cross-import #312 internals; the coordination
  surface has to be Protocol-based.
- Kent's filing rhythm is quarterly VAT (303), annual VAT summary (390),
  quarterly direct-estimation IRPF prepayment (130). That intersection —
  where a ruleset, a PDF extractor, and a history parser all already
  exist — defines Tier 1. Everything else requires upstream parser work
  that lives outside this PR.
- The live-write safety charter (issue #116) is non-negotiable: six
  non-negotiable rules protect against accidental test filings. The
  reconciler must be structurally incapable of writing, not merely
  disciplined against writing.
- Cl@ve-movil 2FA is the one sanctioned human touchpoint on live paths;
  the project mandate forbids mocking, patching, or stubbing around it.
  `AeatAccessGate` and `AeatGateEnvSnapshot` already handle the env-var
  gating; issue #239 must consume them as-is.
- Project mandate: every boundary-crossing record is a strict, frozen
  pydantic v2 model with `extra="forbid"`. Every Python module lives
  under `src/aeat/<subpackage>/`. Live tests gate on
  `AEAT_LIVE_TESTS_ENABLED` via `aeat.entrypoints.cli._live.requires_live_enabled()`.

## Constraints

- **Zero writes.** No state-changing AEAT interaction in any code path
  introduced by this ADR. The reconciler must be structurally incapable
  of mutating AEAT state — no `page.fill`, `page.click`, `page.submit`,
  no `requests.post` / `session.post`, no public method whose name
  suggests a write (`submit`, `send`, `commit`, `finalize`, `presentar`,
  `enviar`, `firmar`, `radicar`, `remitir`). This constraint is enforced
  in five layers described in the Implementation section.
- **Cl@ve-movil 2FA is the sole sanctioned human touchpoint** on live
  paths. No mocks, no stubs, no patches around the approval step.
- **The post-auth AEAT domain is undiscovered territory** from a typed
  perspective, and the PR landing issue #239 is deliberately a mono-PR
  covering both domain modelling and reconciliation. It will be large;
  the alternative is a half-typed surface that drags on for multiple
  coordination rounds.
- **Strict pydantic v2**: `model_config = ConfigDict(strict=True,
  frozen=True, extra="forbid")` on every record. Discriminated unions
  use `Annotated[..., Field(discriminator="kind")]`.
- **Public-API discipline**: every exported symbol goes through
  `__init__.py`. Private modules are `_`-prefixed and not imported by
  consumers outside the subpackage.
- **Live-test gate**: `AEAT_LIVE_TESTS_ENABLED=1` via
  `aeat.entrypoints.cli._live.requires_live_enabled()`. Never
  `@pytest.mark.skipif(os.environ.get(...))`. The env var is
  `AEAT_LIVE_TESTS_ENABLED` (not `AEAT_LIVE_TESTS`) — the project has
  been bitten by the shorter misspelling historically.
- **Module location**: all new Python code under `src/aeat/<subpackage>/`.
  No drift outside the src-layout.
- **No modifications** to `aeat.application.verification` (owned by #301), to
  `aeat.adapters.outbound.aeat.auth` internals (owned by #281), to `aeat.application.sync._divergence`
  enums (consume only), to `aeat.application.filing` approval state (owned by
  #230), to notification-centre parser internals (owned by #312 —
  Protocol-stubbed only), or to `AEAT_LIVE_SUBMIT_*` env vars / the
  submit gate (owned by #117).

## Implementation

The implementation introduces two new subpackages and a CLI verb. All
records are strict, frozen, `extra="forbid"` pydantic v2. No record in
either subpackage carries a `"write"` literal.

### 1. `aeat.remote` — read-only post-auth AEAT domain model

```
src/aeat/remote/
    __init__.py                 # public API exports
    _schema.py                  # RemoteFiling, RemoteExpediente,
                                # RemoteNotification, RemoteReceipt,
                                # RemoteNavigationGraph,
                                # RemoteFilingRef
    _enums.py                   # RemoteFilingStatus (closed StrEnum)
    _filing_detail.py           # FilingDetail{130,303,390,...} per-modelo
                                # casilla aggregates (Tier 1 in this PR)
    _protocols.py               # RemoteFilingFetcher, NotificationReader
                                # typing.Protocols duck-typing StatusReader
    _adapters.py                # StatusReader -> RemoteFilingFetcher
                                # composition adapter (private)
    test_schema.py
    test_no_write_surface.py    # structural write-guard grep test
```

Every record in `aeat.remote` carries a Layer 1 write-guard marker:

- `mode: Literal["read"] = "read"` — strict literal field on every
  boundary-crossing record.

Record catalogue (field names + types only; plan phase fleshes full class
bodies):

- `RemoteFiling` — authoritative AEAT record for one `(modelo, period)`
  submission. Fields: `modelo: ModeloIdentifier`, `period: FiscalPeriod`,
  `expediente_id: str`, `status: RemoteFilingStatus`, `raw_status: str`,
  `submitted_at: datetime`, `casillas: tuple[RemoteCasilla, ...]`,
  `receipts: tuple[RemoteReceipt, ...]`, `complementaria_of: str | None`,
  `mode: Literal["read"]`.
- `RemoteCasilla` — one casilla value as AEAT reports it. Fields:
  `casilla_id: str`, `raw_value: str` (uncoerced string as AEAT prints),
  `data_type: CasillaDataType` (resolved via `aeat.domain.casillas.CasillaRecord`),
  `coerced_value: Decimal | str | bool | None`, `mode: Literal["read"]`.
- `RemoteExpediente` — expediente wrapper. Fields: `expediente_id: str`,
  `filings: tuple[RemoteFiling, ...]` (may include original +
  complementarias), `opened_at: datetime`, `modelo: ModeloIdentifier`,
  `period: FiscalPeriod`, `mode: Literal["read"]`.
- `RemoteNotification` — notification-centre entry (Protocol-stubbed for
  PR #312). Fields: `notification_id: str`, `subject: str`,
  `issued_at: datetime`, `acknowledged_at: datetime | None`,
  `linked_expediente_id: str | None`, `mode: Literal["read"]`.
- `RemoteReceipt` — acuse / receipt PDF metadata. Fields:
  `receipt_id: str`, `kind: Literal["acuse", "justificante"]`,
  `pdf_url: AnyHttpUrl`, `content_hash: str`, `captured_at: datetime`,
  `mode: Literal["read"]`.
- `RemoteNavigationGraph` — stable URL + selector catalogue for the
  post-auth surface (promotes the provisional constants inline in
  `aeat.status._reader` into a typed record). Fields:
  `expedientes_list_path: str`, `expediente_detail_template: str`,
  `notificaciones_path: str`, `mode: Literal["read"]`.
- `RemoteFilingRef` — lightweight reference for report payloads.
  Fields: `expediente_id: str`, `modelo: ModeloIdentifier`,
  `period: FiscalPeriod`, `captured_at: datetime`,
  `mode: Literal["read"]`.
- `FilingDetail130`, `FilingDetail303`, `FilingDetail390` — Tier 1
  per-modelo filing-detail records. Each wraps a `RemoteFiling` plus
  the modelo-specific structured projection already parseable via
  `aeat.history._parsers`. These are the records `fetch_filing_detail`
  returns today as untyped tuples; this ADR types them.

`RemoteFilingStatus` is a closed `StrEnum`:

- `PRESENTADA`, `EN_TRAMITACION`, `RECHAZADA`, `SUBSANADA`,
  `COMPLEMENTARIA`, `ANULADA`, `UNKNOWN`.

Unknown AEAT status strings land in `UNKNOWN` and carry the raw Spanish
prose in `RemoteFiling.raw_status`. Parsing emits a `logging.warning`
with the unknown string and the modelo/period context. Downstream, any
`RemoteFiling` whose `status == UNKNOWN` feeds a `FILING_STATUS_DIVERGENCE`
into the reconciliation report without aborting the run. This keeps the
surface forward-compatible with new AEAT status strings without forcing
a schema migration.

Tier scoping:

- **Tier 1 (in this PR):** 130, 303, 390 — already returned by the
  provisional `fetch_filing_detail` with history parsers live.
- **Tier 2 (in this PR if research shows low risk; otherwise
  follow-on):** 111, 115, 131, 180, 190, 100. All have rulesets or
  extractors, none have history parsers. The plan phase decides which
  of these ship in the same PR vs. land as follow-on issues gated on
  the corresponding parser PR.
- **Tier 3 (follow-on):** 347, 349, 123 (informational). Itemised-list
  modelos have no numeric casilla surface worth reconciling at
  first-round granularity.

Protocols in `_protocols.py`:

- `RemoteFilingFetcher` — given `(modelo, period)`, returns
  `tuple[RemoteFiling, ...]` or a sentinel indicating "no matching
  expediente". Duck-types `StatusReader.fetch_filing_detail`.
- `NotificationReader` — given a filing, surfaces associated
  `RemoteNotification` records (acuses, requerimientos). Duck-types
  `StatusReader.fetch_notificaciones`.

No cross-imports of PR #312's private modules. The adapter in
`_adapters.py` wraps `aeat.status.StatusReader` + `aeat.history.HistoryFetcher`
to satisfy both Protocols. When PR #312 lands, the adapter picks up the
real `fetch_notificaciones` implementation automatically via the existing
structural-conformance pattern.

### 2. `aeat.application.filing.reconciliation` — comparator and Kent-observable report

```
src/aeat/application/filing/reconciliation/
    __init__.py                 # public API: reconcile,
                                # ReconciliationReport,
                                # FilingDivergenceKind,
                                # CasillaDelta
    _schema.py                  # ReconciliationReport, CasillaDelta,
                                # FilingDivergencePayload discriminated
                                # union
    _enums.py                   # FilingDivergenceKind (closed),
                                # ReconciliationOutcome
    _reconcile.py               # reconcile(draft, remote) -> Report
    _sync.py                    # sync-run integration glue (APPROVED
                                # gate, DivergenceRecord sink)
    _cli.py                     # aeat filing reconcile <draft-id>
    test_reconcile.py
    test_no_write_surface.py
```

`FilingDivergenceKind` (closed, disjoint from
`aeat.application.sync._divergence.DivergenceKind`):

- `CASILLA_VALUE_MISMATCH` — local and remote both report a value for
  the casilla; they disagree outside rounding tolerance.
- `CASILLA_MISSING_LOCAL` — AEAT reports a casilla the local draft
  never set.
- `CASILLA_EXTRA_LOCAL` — local draft has a value AEAT does not.
- `FILING_STATUS_DIVERGENCE` — local draft status (e.g.
  `APPROVED`) disagrees with `RemoteFilingStatus`, or the remote
  status is `RECHAZADA` / `ANULADA` / `UNKNOWN`.
- `ROUNDING_ONLY` — delta within `Decimal("0.01")` tolerance shared
  with `aeat.application.verification`.
- `FILING_NOT_YET_FOUND` — AEAT has no record of the `(modelo, period)`
  expected by the local draft.

Kent-observable outcome enum (the terminal triad from issue #239):

- `ReconciliationOutcome.MATCH` — zero divergences of any kind, or only
  `ROUNDING_ONLY` entries.
- `ReconciliationOutcome.DIVERGENT` — any divergence except
  `FILING_NOT_YET_FOUND`. Rounding-only entries do not flip
  `MATCH` to `DIVERGENT`.
- `ReconciliationOutcome.NOT_YET_FOUND` — `FILING_NOT_YET_FOUND`
  present. Mutually exclusive with any other divergence kind: if
  AEAT has no record, per-casilla comparison is undefined.

Outcome mapping is enforced by a static `MappingProxyType` table that
mirrors the `aeat.application.sync._divergence` classification pattern — deterministic,
not heuristic. Reviewers see the kind-to-outcome binding in one place.

`CasillaDelta`:

- `casilla_id: str`
- `kind: FilingDivergenceKind` (discriminator)
- `local_value: str | None`
- `remote_value: str | None`
- `delta: Decimal | None` (populated for `CASILLA_VALUE_MISMATCH` and
  `ROUNDING_ONLY`)
- `narrative: Translatable` (es/en/hu) — Kent-readable reason
  line; follows the `aeat.application.verification.ClassifiedDiscrepancy.narrative`
  precedent.

`ReconciliationReport` (strict, frozen, `extra="forbid"`):

- `status: Literal["match", "divergent", "not_yet_found"]`
- `casilla_deltas: tuple[CasillaDelta, ...]`
- `remote_ref: RemoteFilingRef | None` (None when
  `NOT_YET_FOUND`)
- `draft_ref: FilingDraftRef`
- `reconciled_at: datetime` (UTC)
- `narrative: Translatable`

The top-level function:

```
def reconcile(
    draft: FilingDraft,
    remote: tuple[RemoteFiling, ...],
    *,
    tolerance: Decimal = Decimal("0.01"),
    now: Callable[[], datetime] = _utcnow,
) -> ReconciliationReport: ...
```

Flow:

1. If `remote` is empty — emit single `FILING_NOT_YET_FOUND` delta,
   return `status="not_yet_found"` with `remote_ref=None`.
2. If `remote` has multiple filings (original + complementarias), pick
   the latest-by-`submitted_at` as the comparison anchor; surface the
   chain in the narrative.
3. Build local casilla map from `draft.values` (filtering None).
4. Build remote casilla map from `RemoteFiling.casillas` using
   `RemoteCasilla.coerced_value`.
5. For each casilla id in either map, classify into one of the
   `FilingDivergenceKind` variants; `ROUNDING_ONLY` when
   `abs(delta) <= tolerance`.
6. Classify filing status: mismatch against expected
   (`draft.approval_state` implies `PRESENTADA` post-upload) yields
   `FILING_STATUS_DIVERGENCE`.
7. Derive `ReconciliationOutcome` via the static kind-to-outcome
   table.
8. Emit the report.

### 3. CLI surface — `aeat filing reconcile`

- Verb: `aeat filing reconcile <draft-id>`.
- Flags: `--modelo M --period P` (explicit override when draft id is
  ambiguous); `--json` (machine-readable output); `--live` (force live
  read even if cache is fresh).
- Exit codes: `0` = `MATCH`, `1` = `DIVERGENT`, `2` = `NOT_YET_FOUND`,
  `4` = live-access error (Cl@ve timeout, auth failure).
- Human-readable output follows the `aeat.application.verification` precedent:
  single-word status at the top, bulleted casilla deltas, narrative tail.
- `aeat verify` stays reserved for `aeat.application.verification`; no alias
  collision.

### 4. Sync-run integration — `aeat sync run` gating

- Reconciliation runs only for `FilingDraft`s in
  `FilingDraftStatus.APPROVED`. Drafts in `DRAFT`, `NEEDS_REVIEW`, or
  `SUBMITTED_LOCALLY_ONLY` (pre-approval) are skipped — reconciling
  against AEAT before the local approval step wastes live-reads on
  drafts that may still churn.
- Within a single `aeat sync run` invocation, all
  `(modelo, period)` reconciliations reuse one `AeatSession`. The
  existing 18-minute `AEAT_SESSION_IDLE_TTL` comfortably covers a
  multi-modelo pass; TTL expiry during a run falls back to the
  existing auth re-establishment path. TTL verification against
  Cl@ve-movil's real behaviour is a plan-phase task.
- Report persistence: when `status` is `divergent` or
  `not_yet_found`, the report is serialised into the existing
  `aeat.application.sync._divergence.DivergenceRecord` sink. The
  `DivergenceRecord` schema shape is reused as-is (record id,
  detected_at, modelo, payload, resolution_state);
  `DivergenceClassification` is reused for the record shell;
  `DivergenceKind` is NOT reused — `FilingDivergenceKind` rides in the
  payload as a parallel, disjoint enum.
- Sync-run summary: divergent and not-yet-found reconciliations show
  up prominently in the run summary, alongside existing schema-level
  divergences. One queue, one surface — Kent does not need to
  remember a separate command.

### 5. Write-guard architecture — five layers

**Layer 1 — structural pydantic marker.** Every boundary-crossing
record in both new subpackages carries `mode: Literal["read"] = "read"`.
No `"write"` literal is defined anywhere in the issue #239 surface — not
as a reserved value, not in a fixture, not in a test stub. Any future
PR that needs a write surface must explicitly widen the `Literal`,
which surfaces loudly in code review.

**Layer 2 — public API contract.** Every exported function / method
from `aeat.remote` and `aeat.application.filing.reconciliation` returns a frozen
pydantic record or a tuple of frozen records. No public symbol is
named `submit`, `send`, `commit`, `finalize`, `presentar`, `enviar`,
`firmar`, `radicar`, `remitir`. The whitelisted Playwright primitive
is `page.goto(..., wait_until="domcontentloaded")` followed by
`page.content()` — the same navigation pattern already used by
`StatusReader.fetch_detail_html`. No `page.fill`, `page.click`,
`page.type`, `page.press`, `page.select_option`, `page.check`,
`page.set_input_files`, `form.submit`, bare `.click()`.

**Layer 3 — unit-test grep guard.** Two unit tests —
`test_no_write_surface.py` under `src/aeat/remote/` and
`src/aeat/application/filing/reconciliation/` — walk every `.py` file in their
tree and fail on any match of:

- `page\.(fill|click|type|select_option|check|press|set_input_files)`
- `form\.submit`
- `\.click\(\)`
- `\b(submit|enviar|presentar|firmar|radicar|remitir)\s*\(`
- `requests\.(post|put|patch|delete)`
- `session\.(post|put|patch|delete)`
- `urllib\.request\.Request\([^)]*method=` combined with
  `(POST|PUT|PATCH|DELETE)`

Both tests also introspect `__all__` and fail on any symbol matching
the English-plus-Spanish write-verb regex
`^(submit|send|ack|acknowledge|mark_|confirm|file_|post_|enviar|presentar|firmar|radicar|remitir)`.
This replicates the template already established by
`src/aeat/status/test_no_write_surface.py`, extended with the
Spanish verb set. No new GitHub Actions workflow is added — the
existing unit-suite step on Ubuntu and Windows picks these up.

**Layer 4 — charter #116 alignment.** The live path consumes the
existing `aeat.adapters.outbound.aeat.auth.AeatAccessGate` plus `AeatGateEnvSnapshot`
records. No new write-gate env vars. No new write-safety helpers.
Audit records emitted by the reconciler capture `AeatGateEnvSnapshot`
so the audit trail shows "live-write gate was OFF when the
reconciler ran". `AeatLiveReadNotEnabledError` from
`aeat.adapters.outbound.aeat.auth.certificate` is the propagated error shape when the
live-read gate is not satisfied.

**Layer 5 — test discipline.** Every live test uses
`aeat.entrypoints.cli._live.requires_live_enabled()` at the top of the test body.
Every live test is marked `@pytest.mark.live_read` (never
`live_write`). Every live test triggers a real Cl@ve-movil 2FA
prompt on first run; Kent approves on his phone. Subsequent runs
within the 18-minute idle TTL resume from storage state. No mocks,
no stubs, no patches around the 2FA step. Scratch fixtures for
known-filed periods come from
`tests/fixtures/pdf_corpus/l3_synthetic/_generators/`; per-filing
live-against-AEAT tests take `(modelo, period)` from env vars and
skip cleanly if unset. The gate env var is `AEAT_LIVE_TESTS_ENABLED`
— not `AEAT_LIVE_TESTS`.

### 6. Out of scope (explicit exclusions)

- Any state-changing AEAT interaction.
- Modifications to `aeat.application.verification` (#301).
- Modifications to `aeat.adapters.outbound.aeat.auth` internals (#281).
- Modifications to `aeat.application.sync._divergence` enums (consume only).
- Modifications to `aeat.application.filing` approval state (#230).
- Notification-centre parser internals (#312 — Protocol-stub only).
- `AEAT_LIVE_SUBMIT_*` env vars or submit-gate plumbing (#117).
- Tier 3 modelos (347, 349, 123 informational).
- Full regional / alternate ruleset variants for reconciliation
  (Canarias IGIC, etc.).

### 7. Acceptance criteria (Kent-observable, from issue #239)

- `aeat filing reconcile <draft-id>` returns `MATCH` 30 minutes post-upload
  for a Modelo 303 quarterly filing whose local draft matches AEAT
  byte-for-byte.
- `aeat filing reconcile <draft-id>` returns `NOT_YET_FOUND` with a
  prominent warning narrative when AEAT has no expediente for the
  expected `(modelo, period)`.
- Casilla-level delta display surfaces when AEAT rounds differently
  (`ROUNDING_ONLY` within `Decimal("0.01")` tolerance classified as
  `MATCH`; anything outside tolerance classified as
  `CASILLA_VALUE_MISMATCH` and reported as `DIVERGENT`).
- `aeat sync run` auto-invokes the reconciler for every approved
  `FilingDraft`, surfaces `DIVERGENT` and `NOT_YET_FOUND` results in
  the run summary, and persists records via the existing
  `DivergenceRecord` sink.

## Rationale

### Naming split — `aeat.remote` and `aeat.application.filing.reconciliation`

Research section 4 established that `aeat.application.verification` already publishes
a Kent-facing verdict vocabulary anchored to the PDF-vs-engine axis —
`VerificationStatus`, `VerificationVerdict`, `verify_declaracion`, and
four `verify`-named CLI verbs. Reusing `aeat.application.verification` for a
separate axis (local-vs-AEAT) would collapse two orthogonal comparisons
onto one name and regress the vocabulary established by #301.

Three alternatives were considered and rejected. An `aeat.reconcile`
top-level subpackage with both domain and reconciler inside pulls the
remote-domain primitives out of line with `aeat.status` and
`aeat.history`, which are already the "how we talk to AEAT"
subpackages. Keeping the remote domain in `aeat.remote` but placing the
reconciler in `aeat.application.sync._reconciliation` dilutes the `aeat.application.sync`
auto-heal invariant — `ADDITIVE` implies safe-to-heal is narrow and
schema-level; filing-instance value divergence must never auto-heal.
An `aeat.verify.remote` sibling of `aeat.application.verification` shares a name
prefix but means something materially different, imposing a high
cognitive cost on every future contributor.

The adopted split cleanly slots `aeat.remote` between `aeat.status`
(raw AEAT primitives) and `aeat.application.filing` (local drafts); the
reconciler lives under `aeat.application.filing.reconciliation` as a sibling to
`aeat.application.filing._import` — the nearest-existing neighbour, also a
local/remote transform in the opposite direction. The CLI verb
`aeat filing reconcile` has no existing collision (research section 4
catalogued `casillas verify`, `submission verify`, `submission diff`,
`setup verify`, `justificante verify`, `vat verify`; no
`reconcile` / `compare` / `match`).

### `FilingDivergenceKind` fork (not extending `DivergenceKind`)

Research section 5 established that `aeat.application.sync._divergence.DivergenceKind`
is the backbone of a statically-enforced auto-heal-safety contract. Its
10 variants are tuned for schema-level drift (corpus additions, ruleset
removals, portal URL changes, etc.) and its classification
`MappingProxyType` is a source-of-truth invariant: `ADDITIVE` means
safe-to-heal. Adding filing-instance value kinds to that enum forces
every future reviewer of the classification table to reason about two
orthogonal axes — schema safety and filing-value safety — and silently
widens the auto-heal surface to value-level divergences that must never
auto-heal.

The fork keeps the proven structural pattern — discriminated union,
frozen strict pydantic, static kind-to-outcome table, `ResolutionState`
reused verbatim — while keeping the vocabulary isolated. Reviewers
looking at `DivergenceKind` classification continue to see only the
schema-safety axis; reviewers looking at `FilingDivergenceKind` see
only the filing-value axis. The `DivergenceRecord` persistence sink is
shared because a single Kent-facing queue is easier to reason about
than two parallel queues; the payload discriminator distinguishes
schema-level from filing-level records at consumer sites.

### Protocol-stub strategy for PR #312

Research section 6 confirmed that PR #312 ships
`StatusReader.fetch_notificaciones`, `LiveAeatNotificacionSource`, and
`build_live_status_reader` across 26 files. Cross-importing PR #312
internals from issue #239 would create a merge-order dependency that
either blocks #239 on #312 or forces a large rebase the day #312
lands.

The adopted strategy declares `RemoteFilingFetcher` and
`NotificationReader` as `typing.Protocol`s in `aeat.remote._protocols`,
duck-typing on the public facade method names
(`fetch_filing_detail`, `fetch_notificaciones`). The adapter wraps
`StatusReader` today (which satisfies `RemoteFilingFetcher` via the
already-wired `fetch_filing_detail` and will satisfy `NotificationReader`
automatically once #312 merges `fetch_notificaciones`). Unit tests for
the reconciler use real Protocol-conforming Python classes — not
`unittest.mock` — per the mandate against mocks and patches. Live
tests gate on the real fetcher availability.

The Protocol surface survives post-merge as the reviewable public
contract; the only change on #312 merge is that the real implementation
satisfies the Protocol, which it already does structurally.

### Tier scoping — 130 / 303 / 390 first

Research section 7 laid out the 17-modelo corpus and confirmed that
history parsers exist only for 130, 303, and 390. The intersection of
"Kent files it regularly" (quarterly VAT, annual VAT summary,
quarterly direct-estimation IRPF prepayment) and "history parser
exists today" is precisely these three. Tier 2 (111, 115, 131, 180,
190, 100) has rulesets and/or extractors but no history parsers; the
plan phase decides whether any of those ship Tier-2 scaffolding in
the same PR or follow on as parser-gated issues. Tier 3 (347, 349,
123) is explicitly deferred — itemised-list modelos have no numeric
casilla surface that reconciles at casilla granularity, and
informational modelos are not on Kent's critical filing rhythm.

Scoping Tier 1 first keeps the PR diff reviewable and matches the
Kent-observable acceptance criteria in issue #239 (the canonical
"filed a 303 on Monday, reconcile on Friday" flow).

### Structural-plus-runtime write guard (vs. runtime-only)

Research section 8 enumerated the existing write-safety infrastructure
around charter #116: the four-factor gate, the three env vars, the sole
`_submit_with_transport` call site, `AeatLiveReadNotEnabledError`,
`AeatGateEnvSnapshot`. All of this is runtime: env var checks that
abort before a write fires.

The issue #239 surface adopts a defence-in-depth posture because the
whole point is that the reconciler has no write path to gate in the
first place. Layer 1 (pydantic `mode: Literal["read"]`) makes a
write-path a type-error. Layer 2 (public API contract) makes a
write-path a code-review failure. Layer 3 (unit-test grep guard) makes
a write-path a red CI build. Layer 4 consumes the existing charter
infrastructure for audit-trail alignment. Layer 5 keeps the live-test
discipline that has already caught the shorter-env-var-name regression
historically. Any single layer failing on its own does not produce a
write — all five must fail simultaneously, which is the defence-in-depth
threshold charter #116 aims for.

### Closed `RemoteFilingStatus` with `UNKNOWN` fallback

Two alternatives were on the table. Raising at parse time on unknown
AEAT status strings would force every future AEAT status addition
into a schema migration before the reconciler works — too brittle
given AEAT's irregular-change history. Free-form `status: str` as the
current `FiledModeloMetadata.status` carries today defeats the purpose
of a typed domain and forces every consumer to re-parse the Spanish
prose.

The adopted approach — closed `StrEnum` with `UNKNOWN` fallback plus
`raw_status: str` — keeps downstream code type-safe, surfaces unknown
statuses to Kent as a `FILING_STATUS_DIVERGENCE` (loud by default,
no silent pass-through), and lets the enum extend via ordinary PR
review as new AEAT statuses surface. The warning log on unknown
parse is the drift signal for the maintainer.

### Rounding tolerance shared with `aeat.application.verification`

Sourcing the tolerance from a new `Settings.aeat_reconciliation_rounding_tolerance`
field offers per-deployment tuning but fragments Kent's mental model:
the PDF-vs-engine verifier accepts 0.01-euro rounding, the
local-vs-AEAT reconciler could accept something else, and Kent sees
two different "rounding" definitions across two CLI verbs. Reusing
`Decimal("0.01")` from `aeat.application.verification` keeps one definition of
"close enough" across the stack.

### Sync-run gating on `APPROVED`

Unconditional reconciliation on every sync blows out the live-read
surface (and the Cl@ve-movil 2FA prompt frequency) for drafts that
have not been uploaded to AEAT yet — there is literally nothing to
reconcile against. Gating on `FilingDraftStatus.APPROVED` matches the
issue #239 acceptance criterion ("30 minutes post-upload") and
respects the Kent-pattern of "do not make me remember" by
auto-invoking once the draft has reached the state where upload has
happened or is imminent.

### Session lifecycle — reuse the existing `AeatSession`

The 18-minute `AEAT_SESSION_IDLE_TTL` comfortably covers a multi-modelo
pass in a single sync run; a per-`(modelo, period)` re-auth would
trigger a Cl@ve-movil prompt per filing, which is hostile to Kent.
Reuse is the defensible default; TTL-expiry handling falls back to
the existing auth re-establishment path in `AeatAuthenticator`. No
new session-lifecycle primitives are introduced. Plan phase confirms
against Cl@ve provider live behaviour before wiring.

## Consequences

- **The PR will be large and the mono-PR shape is deliberate.** The
  post-auth AEAT domain is undiscovered territory from a typed
  perspective; splitting "introduce `aeat.remote`" from "introduce
  reconciler" across two PRs produces a half-typed surface that
  drags on through multiple coordination rounds. The five-layer
  write guard means the PR is safe to be large.

- **Tier 2 modelos (111, 115, 131, 180, 190, 100) may slip to
  follow-on PRs.** The plan phase makes the call per-modelo based on
  whether the history parser lands in the same PR or ships
  separately. Tier 3 (347, 349, 123) is explicitly deferred. Kent's
  critical rhythm (Tier 1: 130, 303, 390) is covered end-to-end in
  this PR.

- **The Protocol-stub indirection adds one import layer for
  `RemoteFilingFetcher` and `NotificationReader` until PR #312
  merges.** Post-merge the indirection remains as the reviewable
  public contract; the adapter implementation does not change.

- **Live tests require a human for Cl@ve-movil 2FA.** This is a
  feature, not a bug — every live test triggers Kent's phone prompt
  on first run. The 18-minute idle TTL means subsequent tests in a
  run resume from storage state without re-prompting. The
  `AEAT_LIVE_TESTS_ENABLED` gate keeps live tests out of CI by
  default.

- **`aeat.remote` becomes a first-class API surface the project
  will carry forward.** Tier 2 / Tier 3 expansion, notification-centre
  composition, receipts, apoderamientos, and any future post-auth
  domain work attaches to `aeat.remote`. The ADR commits the project
  to carrying this surface as a load-bearing consumer of the
  AEAT-authenticated session.

- **Divergence persistence shares the existing sync sink.** One
  Kent-facing queue handles both schema-level and filing-level
  divergences. Sync-run summary surfaces `DIVERGENT` and
  `NOT_YET_FOUND` reconciliations prominently alongside the existing
  schema-level divergence classes; the run output gets longer but
  stays in one place.

- **The `FilingDivergenceKind` enum is a parallel vocabulary to
  `DivergenceKind` and future contributors need to pick the right
  one.** ADR docstrings on both enums and the public API reference
  document the split. A third enum covering a third divergence axis
  would warrant a reconsideration, but two is tractable and the
  alternative (collapsing both into a single enum) regresses the
  auto-heal-safety invariant.

- **`RemoteFilingStatus.UNKNOWN` will surface as
  `FILING_STATUS_DIVERGENCE` the first time AEAT ships a new status
  string.** This is the intended behaviour — loud warn-and-continue
  beats silent pass-through — but operators should expect a
  divergence-queue spike the first day a new AEAT status hits
  production, followed by an enum-extension PR.

- **The write-guard grep tests will fail loudly on any attempt to
  add a write-path to either subpackage.** This is the intended
  behaviour and the primary reason the PR can be large. Future
  write-surface work goes through `aeat.adapters.outbound.aeat.export` and the
  existing four-factor gate, not through `aeat.remote` or
  `aeat.application.filing.reconciliation`.
