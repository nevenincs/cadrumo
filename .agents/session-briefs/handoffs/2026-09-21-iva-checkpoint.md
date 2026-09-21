# IVA-01 implementation checkpoint

Updated: 2026-09-21
Status: Phase 0 and Phase 1 complete; Phase 2 capture/readback in progress

## Session identity

- Brief: IVA-01 revision 0.6
- Policy: session-policy revision 1.4
- Acceptance pattern: ACCEPTANCE-01 revision 1.3
- Provider, cc number, UUID: pending; not invented
- Worktree: `Y:/code/cadrumo-worktrees/tui-modelo`
- Branch: `tui/modelo`
- Phase-0 starting HEAD: `57595ff38871cc87bfb703653074c8521e27f20a`
- Phase-0 installed-probe final HEAD: `28990e3c6e3d84d2cfcedc23ea72a2957aae02c4`
- Earlier IVA audit baseline: `ce2c87ce4ceafbbe912c5a15500c8ec06be1979e`
- Income-reported authority generation to reconcile: `86e40c0d92f716797360cf97cb48aac4d05f206bd9c117331424ef905cda6e7b`

## Goal and acceptance state

First milestone: one runnable, coherent synthetic invoice/ledger-to-Modelo-303
slice through supported installed runtime and canonical authority. Current audit
disposition is V1-V9 partial and V10-V11 failed. Durable source findings are in
`.vault/reference/2026-09-21-iva-workflow-reference.md`.

## Active ownership and constraints

- Other sessions currently own uncommitted income/authority/export changes.
  Preserve them and do not edit overlapping files without coordination.
- IVA session currently owns this checkpoint and the IVA workflow reference.
- No live AEAT submission, real-taxpayer mutation, authority fabrication,
  validation bypass, import-path trick, or second ledger/authority/runner.
- No verification reservation has been made in Phase 0. Unchanged passing tests
  from the audit are retained and will not be repeated.

## Named agent

- Luna Runtime Reconciler: read-only comparison of income and IVA runtime,
  package and authority identities, manuals build failure, and changes since the
  audit. No edits, tests, builds, installs, authority publication, decisions, or
  children. Report is capped at 600 words with exact path/line evidence and
  checks marked NOT RUN. Stop at facts, bounded unknowns, or actionable blocker.
- Luna report completed against HEAD `57595ff38871cc87bfb703653074c8521e27f20a`.
  It found that the old income generation and current IVA environment are not
  the same reproducible installation. No original income executable/package/
  source fingerprint or authority descriptor was retained.
- Luna Phase-1 mapping completed against HEAD `28990e3c...`: invoice facts and
  transaction ledger/tax facts are intentionally separate owners; links are
  atomic associations only. One invoice can link to several transactions; a
  transaction has one invoice reference; split cash-accounting payments are
  transaction evidence parts. No totals-copy correction is justified.
- Luna completeness trace found a real bounded gap: rejected selected-scope IVA
  rows yield generic aggregation diagnostics and no observation/source ID, but
  only unrouted quantities become durable blocking source issues. Verification
  and export do not consume all generic IVA diagnostics. Reviewed-excluded and
  out-of-period/profile rows remain intentional exclusions.
- Sol IVA Completeness Adviser is active on the single question of the smallest
  fail-closed selected-scope diagnostic rule. Adviser is consult-only and will
  return idle after its recommendation.
- Accepted decision: `.vault/adr/2026-09-21-iva-workflow-adr.md` chooses an
  explicit typed blocking classification for selected-scope financial evidence
  failures, durable source-issue persistence, and verification/export refusal.
  It excludes reviewed exclusions, legitimate filtering and informational
  invoice differences; it introduces no waivers or totals copying.
- Luna's implementation map identifies the existing durable channel as
  `CalculationRevision.source_issues`. Clear blocking reasons are missing base,
  IVA amount/rate, EUR substrate, supported currency/rate, deduction and required
  counterparty facts, plus zero-rate/category/counterparty contradictions.
  Unsupported direction/business state/category, rate-table-window, and the
  observation-preserving prorrata diagnostic remain unchanged pending separate
  grounding.
- Terra IVA Completeness Principal owns the bounded shared implementation in
  aggregation binding projection, calculation revision/source staging,
  verification/export gates, the source-issue domain type, and focused tests.
  All named production files were clean when ownership was assigned.
- Terra Manuals Build Principal: owns only the minimal Hatchling compatibility
  repair in `packaging/cadrumo_data_manuals/hatch_build.py` and directly related
  package tests. It may read but not edit the authority hook used as precedent.
- Terra Phase-0 Runtime Executor: completed the isolated frozen installation
  and read-only installed probes. Retained runtime is under
  `C:/Users/hello/AppData/Local/Temp/cadrumo-iva-phase0-d4b3d8c41d274dd2b4dce7db5d9f09ba`.

## Known evidence entering Phase 0

- The earlier IVA environment had no default `authority.current.json` and could
  not install the workspace because the local manuals build failed at
  `packaging/cadrumo_data_manuals/hatch_build.py:86`.
- Dependency-only sync allowed source-path pytest but did not establish an
  installed `aeat` executable.
- Income now reports installed execution for year 2025 and the authority
  generation named above. This discrepancy is unresolved; neither observation
  is assumed to supersede the other.
- The current `.authority/authority.current.json` instead selects generation
  `804b2...` and its declared database digest matches. Its source registry has
  filing-grade 2025 Modelo 303 periodic and Modelo 390 `0A` definitions, but
  this metadata does not prove installed calculation or export behavior.
- The current environment still resolves no installed `aeat` executable or
  installed `cadrumo` package. The income ledger's old executable identity is
  not recoverable from the evidence inspected so far.
- `packaging/cadrumo_data_manuals/hatch_build.py` retains a two-parameter generic
  annotation incompatible with the admitted Hatchling backend. The analogous
  authority hook contains a compatibility treatment, but is dirty and owned by
  another session; it is precedent only.
- Root cause repaired in both corpus companion hooks without changing admitted
  dependencies or validation. Focused compatibility tests: 2 passed. Isolated
  manuals and official wheel builds: passed.
- Frozen active sync into the retained isolated venv installed 227 packages.
  Installed `aeat` reports CADRUMO 0.5.1. Canonical read-only descriptions for
  Modelo 303/2025/4T and Modelo 390/2025/0A both selected revision 2025 and
  exited successfully.
- Runtime authority: generation
  `804b2c4f09b6c7d7292af3f77568f5c9772176dea5a49b2bd90c69615e4cd1fd`;
  descriptor SHA-256
  `4fb2310444622229c8aa70af3531b6a6365709ba135375cf69d3cf666b6313b5`;
  declared and actual database SHA-256
  `b06e3565ce5373a749aabbc1ef57e2450d1472a33dada1c64084db87014ad564`.
- The installation is editable and HEAD advanced during the run. Re-establish
  source identity immediately before each acceptance claim; do not describe it
  as an immutable wheel installation.
- The active branch advanced and has dirty files owned by income/authority and
  export work. Phase 0 is read-only until ownership and effective runtime are
  reconciled.

## Next bounded actions

1. Phase-0 reservation completed successfully; no active process remains.
2. Luna Phase-1 Contract Mapper: trace the delta for ownership and precedence
   across canonical invoice details, transaction monetary/tax facts, deduction
   evidence, links, partial/multiple relationships, corrections, and
   incomplete/contradictory calculation behavior. Read-only, no tests.
3. Coordinate any shared invoice/ledger edit with income and assets ownership.
4. Escalate genuinely undefined precedence/reconciliation rules as a bounded
   adviser decision packet before implementation.

## Active Phase-1 verification reservation

- Owner: Terra IVA Completeness Principal.
- Exact selection reserved: focused IVA aggregation/source-issue persistence,
  ledger evidence verification gate, and export evidence gate test files under
  `src/cadrumo/application/modelo/tests/`, run with
  `uv run --no-sync pytest -q -n0`; targeted Ruff and strict typing only for
  changed modules after the regressions pass.
- Status: reserved, not started. No aggregate lane or installed acceptance run is
  reserved by this slice.
- Phase-1 principal result: production implementation plus focused projection,
  verification and export regressions pass (61 tests); targeted Ruff and narrow
  basedpyright pass. The implementation persists only the 14 accepted reasons as
  `iva_selected_scope_evidence_failure` with sanitized `transaction:<id>` refs.
- Active locale reservation — owner: Terra IVA Locale Executor; exact files are
  the four clean `src/cadrumo/locales/{en,es,ca,hu}/application.yml` catalogues
  and the focused verification-report locale test. Reserved checks:
  `test_modelo_verification_report_view.py`, `test_placeholder_parity.py`, and
  `test_locale_coverage_inventory.py`, with `-q -n0`, plus targeted Ruff for an
  edited Python test. Status: complete: parity/inventory 5 passed (9 integration
  cases intentionally deselected), explicit integration rendering 10 passed,
  Ruff and diff check passed.

## Phase-1 completion

- Acceptance advanced: V2 selected-scope completeness contract implemented;
  V2 remains partial until an installed capture-to-303 journey is proven.
- Root cause: typed IVA aggregation failures were transient and absent from the
  persisted calculation source mesh.
- Existing owners extended: typed source diagnostic, Modelo binding resolver,
  `CalculationRevision.source_issues`, verification and export evidence gates.
- Exactly 14 missing/unsupported/contradictory reasons block. Ambiguous authority
  or classification reasons, reviewed exclusions, out-of-period rows and the
  observation-preserving prorrata diagnostic remain unchanged.
- Durable evidence is sanitized to a reason plus `transaction:<id>`; no raw
  financial values are persisted in the source issue.
- Focused source-mesh/projection/verification/export selection: 62 passed.
  Targeted Ruff and basedpyright: clean. Four-locale rendering: 10 passed.
- Accepted decision: `.vault/adr/2026-09-21-iva-workflow-adr.md`.
- Next bounded action: Phase 2 Luna delta for canonical multi-line public write,
  structured readback, secure import provenance and deduction/prorrata write
  surfaces. Coordinate shared invoice/ledger files before edits.

## Active Phase-2 slice

- Luna Phase-2 mapping completed read-only at HEAD `baafa3748c`. The shared
  catalogue writer already accepts ordered `InvoiceLine` values and the encrypted
  repository reopens them. The CLI remains scalar and structured readback omits
  canonical document and line facts. Bulk import retains a row number during
  parsing but no accepted-record source digest/row identity.
- Existing transaction commands already expose IVA facts, deduction kind,
  business-use allocation, prorrata reference/sector and purchase-evidence
  linkage. This slice does not create another transaction or evidence writer.
- Accepted decision:
  `.vault/adr/2026-09-21-iva-workflow-cli-invoice-lines-adr.md` chooses one
  repeatable `--line` JSON object per canonical invoice line, preserves order,
  performs no frontend arithmetic and refuses mixed scalar/structured input.
- Import provenance follows the existing `RawProvenance` shape: basename,
  SHA-256 and one-based row only. No original path or raw row is persisted.
- Terra Phase-2 CLI Principal owns only the invoice CLI command/spec/projection
  surfaces and directly related tests. Reserved checks: focused catalogue
  invoice payload/command tests with `-q -n0`, followed by targeted Ruff and
  strict typing for edited modules. It must not edit invoice domain persistence,
  bulk import, TUI, ledger calculation, locales or authority files.
- Terra Phase-2 Provenance Executor owns only the canonical invoice provenance,
  bulk-import capture, encrypted round-trip and focused import/persistence tests.
  Reserved checks: focused bulk-import and secure-storage round-trip tests with
  `-q -n0`, followed by targeted Ruff and strict typing. It must stop if reuse of
  the existing provenance type requires an architectural relocation or creates
  a domain dependency violation.
- Both agents are working in a shared tree and must preserve peer and other-session
  changes. Neither may run broad lanes or commit until its bounded result has been
  reviewed and the two slices are reconciled.

## Phase-2 completion

- Acceptance advanced: V1 canonical CLI capture/readback and secure import
  provenance are implemented; V2 has a complete shared write surface for invoice
  lines while transaction IVA/deduction/allocation/prorrata facts continue through
  the pre-existing ledger operations. Installed capture-to-303 acceptance remains
  outstanding.
- Root causes: the CLI exposed only scalar base/rate and omitted canonical fields
  from structured output; the application writer still required a caller-computed
  base beside supplied lines; accepted bulk-import rows lost their source identity.
- Existing owners extended: catalogue application writer, invoice CLI command/spec
  and payload, canonical `Invoice`, bulk import, and encrypted catalogue roundtrip.
- Repeatable `--line` accepts one strict JSON object per occurrence, preserves
  order, refuses mixed scalar input before mutation, and delegates all totals to
  the application/domain owner. Mixed RATE_21/RATE_10 regression coverage passes.
- Structured readback now requires at least one canonical line and includes invoice
  class, series, operation date/role, IVA category and rectification reference.
- Bulk import reads the source bytes once, records basename, SHA-256, one-based row,
  format, ingest time and provider label, and retains that exact association across
  encrypted save/reopen. Absolute paths and raw rows are not persisted.
- The existing `RawProvenance` type remains the single owner for this bounded slice.
  Import-linter keeps the Domain boundary, no cycle or qualified-class persistence
  exists, and neutral relocation would touch roughly 160 cross-session import sites.
  No duplicate or compatibility alias was introduced.
- CLI/application focused selection: 22 passed; explicit CLI integration: 16
  passed; final command-spec help wiring: 2 passed. Provenance focused selection:
  4 passed with 22 marker-deselected; explicit CSV/TSV/XLSX, one-read and encrypted
  import-to-reopen nodes: 5 passed. Locale parity/inventory: 5 passed. Targeted
  Ruff, formatting and basedpyright passed; scoped diff checks passed.
- Import-linter was also run once as the affected integrated boundary gate: Domain
  remained KEPT and no IVA dependency was reported. The command remains globally
  non-zero on five pre-existing/cross-session contracts, including the concurrent
  `dev.acceptance` exhaustive-lane addition and unrelated test-layer imports.
- Phase-2 implementation was prepared on moving shared branch base
  `5f70f630e84881b76790958caff6008feddffda1` and integrated as
  `c635e2cc3096bfa603f6be39140388420506374f`. Other sessions' income, assets,
  withholding, calendar and TUI changes remained unstaged.

## Active Phase-3 temporal and settlement work

- Luna mapped the existing carry, annual partition, secure period history,
  filing-chain supersession and wallet reconciliation owners at HEAD
  `f72ef01f760f87bbe36e83016ed6393921335090`. Dirty shared history, operation,
  CLI and TUI lifecycle surfaces remain out of IVA ownership.
- Annual completeness root cause: the Modelo 390 IVA compensation partition
  emitted generic unresolved diagnostics that were not persisted, so export
  could not see missing or stale required Modelo 303 evidence.
- Existing owners now emit the typed durable reason
  `iva_compensation_annual_source_evidence_failure` only for actual unresolved
  annual bindings. It persists on the calculation revision, produces a distinct
  localized blocking verification finding and refuses export. Contradictory
  evidence continues to refuse upstream before revision persistence.
- Annual focused partition/projection/verification/export selection: 35 passed;
  targeted Ruff and basedpyright passed. Four-locale parity/inventory: 5 passed;
  explicit verification rendering: 11 passed.
- Existing replay/amendment behavior is now pinned: saving the same period state
  twice yields one period and one compensation lot; an amended current filing
  preserves the superseded original's AEAT register and external evidence.
  Focused replay/filing-chain selection: 28 passed.
- Accepted settlement decision:
  `.vault/adr/2026-09-21-iva-workflow-settlement-lifecycle-adr.md` extends the
  existing immutable filing record with an IVA settlement evidence snapshot.
  Filing-chain identity/supersession stays authoritative; compensation history
  remains the only active credit arithmetic owner. Calculation/export cannot
  imply payment, approval or refund payment.
- Settlement implementation is not yet assigned. The smallest clean slice is
  domain invariants, encrypted filing-catalogue roundtrip and same-identity
  application mutation. CLI/history/TUI public surfaces are currently blocked
  by active peer ownership and must be coordinated rather than overwritten.
