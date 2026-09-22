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
- Settlement Amendment 1 is accepted and re-attested. Every new local Modelo 303
  filing derives its snapshot inside the existing filing co-commit from the core
  canonical result casillas and the exact `IvaCompensationPeriodState` also
  written to secure history. Missing required state refuses persistence; legacy
  records may remain `settlement=None` and explicitly incomplete.
- Payment evidence is an ordered immutable tuple. Identical entries collapse,
  same-reference conflicts and totals above liability refuse, and payment amount
  and state are derived. Local refund election intent remains separate from the
  evidence-gated official refund state.
- Focused independent verification: core/domain 17 passed; encrypted filing
  persistence 1 passed; real local-M303 filing path 1 passed; targeted Ruff,
  Ruff formatting, basedpyright and scoped diff checks passed. The real path
  proves the filing snapshot credit copy equals the co-committed compensation
  history. Supersession preservation remains covered by the earlier filing-chain
  regression rather than a second full settlement filing scenario.

## Active Phase-4 installed acceptance blocker

- Installed CLI registration and export owners are mapped. Invoice linking is
  identifier-only; it does not establish IVA amount, classification or deduction
  facts. Semantic export validation already parses the written artifact and is
  separate from receipt size/digest binding.
- Smallest blocker: Modelo 303 calculation requires a pre-existing typed
  `FilingInstanceEvidence` JSON through `--m303-filing-evidence`. The installed
  public CLI reads and validates that file but exposes no public operation to
  create it; creators found so far are test-only. A pure installed CLI journey
  therefore cannot yet establish all required inputs through supported public
  writes.
- Next bounded action: define and implement only the missing M303 filing-evidence
  creation seam through an existing shared owner, then run one installed 2025
  M303 capture/reopen/calculate/verify/export journey before expanding to the
  four-period and Modelo 390 acceptance scenarios. Do not use test helpers or
  fabricate evidence for acceptance.
- Settlement implementation and its checkpoint were committed as `52cbf47ed5`.
- Production authoring evidence and the accepted boundary are now durable in
  `.vault/reference/2026-09-21-iva-workflow-m303-filing-evidence-authoring-reference.md`
  and `.vault/adr/2026-09-21-iva-workflow-m303-filing-evidence-authoring-adr.md`,
  committed as `99a1102b8e`. A transient shared application operation must own
  composition; callers may supply only genuine assertions and secure references,
  never authority/profile/calculated fields. Optional branches refuse until fully
  grounded.
- Application implementation stopped without edits on one tighter blocker: even
  the ordinary path requires an exonerado-390 non-applicability reference, while
  `FilingEvidenceReference` is only nominal. Current calculation ports cannot
  resolve its role, profile/taxpayer scope, period or freshness. Inventing a
  reference would violate the accepted decision.
- Active Luna audit is limited to the existing secure evidence bundle/attachment
  owner: determine whether its stored metadata can ground that non-applicability
  assertion and, if not, the smallest typed metadata/resolver extension that
  preserves the existing store.
- Secure-owner audit completed: encrypted `AttachmentStore` is the reusable
  custody owner; purchase-invoice evidence and `EvidenceBundle` lack filing-role
  semantics. Attachment already owns bucket scope, ID/digest, encrypted bytes,
  capture time and custody, but needs a canonical typed applicability payload.
- Authoring ADR Amendment 1 accepts an operator `not_applicable` attestation as
  evidence of that assertion (not AEAT acceptance). The payload binds the closed
  role, year/period, observation instant and the existing authenticated profile
  witness `(profile_id, record_revision, content_digest, schema_id,
  schema_version)`. Any profile revision makes it stale. Conflicting assertions
  block; absence never implies non-applicability; `applicable` stays unsupported
  until the optional branch is fully grounded.
- Terra principal now owns only secure in-memory admission and exact resolver on
  the existing attachment store plus focused persistence/application tests. CLI
  wiring and ordinary envelope composition wait for that slice.
- Secure attestation slice completed: a dedicated attachment kind carries one
  canonical encrypted payload; admission creates bytes in memory and returns a
  digest-bound `FilingEvidenceReference`; resolution verifies custody, bucket,
  current profile witness, exact 2025 quarterly coordinate, timing and all
  same-coordinate typed assertions. `applicable` refuses before mutation,
  conflicts block, and legacy attachments remain valid but ineligible.
- The attachment manifest remains V1 because its grammar and metadata fields did
  not change; typed semantics live only in the encrypted blob. Independent
  verification: 14 focused domain/attachment-store tests passed; targeted Ruff,
  formatting, basedpyright and scoped diff checks passed. No broad lane or
  import-linter was rerun.
- Next bounded action: compose the ordinary filing envelope using the resolver,
  then expose secure attestation collection and that transient authoring request
  through the installed CLI without full-envelope plaintext input.
- Ordinary envelope composition completed: the transient request accepts only
  the exact coordinate, joint-return and annual-volume elections, and the secure
  applicability reference. It derives current profile scope, pinned annual Orden
  snapshot, empty general-scope rows and calculation result through production
  owners, then validates the existing `FilingInstanceEvidence`. Simplified or
  mixed profile scope refuses as unsupported; no draft is persisted.
- Independent authoring verification: 4 focused real custody/profile/authority
  tests passed; targeted Ruff, formatting, basedpyright and diff checks passed.
- Next bounded action is installed CLI wiring: secure attestation collection and
  ordinary transient authoring must feed the existing calculate action directly;
  the full-envelope plaintext file remains internal/legacy and is not production
  authority.
- Installed CLI hard-cut implemented pending independent integration: new
  `app modelo work attest-m303-exonerado-390` admits the fixed non-applicable
  assertion and emits separate safe `attachment_id`/`sha256` fields. Global
  object-key redaction remains unchanged; the composite reference stays internal.
- M303 calculate and quickfile now accept explicit positive/negative choices for
  joint-return and annual-volume facts plus separate attachment ID/digest. The
  application owner validates and constructs the internal reference. Public
  `--m303-filing-evidence` and its plaintext loader/contract test are removed;
  non-M303 behavior remains unchanged. One preloaded authenticated profile is
  reused through authoring/resolution.
- A new real 2025 1T CLI integration passes: secure attestation, authority work
  creation, canonical linked sale/purchase evidence, wallet/source mesh,
  calculation save and encrypted revision reopen. It proves persisted ordinary
  filing evidence and exactly one profile decrypt during calculate. Verify/export
  and successful quickfile remain outside that test.
- No-legacy test migration completed. Ordinary CLI tests now reuse one secure
  2025 attestation/options helper; simplified and mixed regime CLI cases assert
  truthful unsupported refusal while their application coverage remains. The
  plaintext test helper is deleted. Production CLI has no old option occurrence;
  tests retain only one intentional absence assertion.
- Wallet guidance correction: a nonzero caller-supplied prior balance with
  missing required prior-period authority now uses the existing typed
  `no_usable_authority` no-action refusal, instead of leaking generic
  `iva-wallet seed --amount 0` prose. Genuine zero/no-input first-profile cases
  retain seed guidance.
- Independent final checks: migrated integration files 11 passed; discovery
  nodes 2 passed; source-mesh nodes 3 passed; local-path 8 passed; focused
  domain/application/spec selection 18 passed. Targeted Ruff, formatting,
  basedpyright and scoped diff checks passed. No broad lane/import-linter ran;
  unrelated M111/M115 work was excluded.
- Installed all-public 2025/1T acceptance now passes in
  `dev/acceptance/iva/cli_journey.py`: profile create/complete, secure purchase
  artifact admission, sale and purchase transactions, canonical issued/received
  invoices and links, purchase deduction classification, fresh-process list
  readback, zero wallet seed, secure applicability attestation, authority work
  create and calculation. No repository seeding or test filing-evidence builder
  participates.
- Independent oracle is `21.00 output IVA - 10.50 deductible input IVA = 10.50`;
  the public calculation projection returned `iva.resultado=10.50`. Focused real
  installed test: 1 passed in 119.92s, log
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T185312.046484Z-pytest-58272-ea70c990/run.log`.
  The sanitized receipt captures executable digest, package/source identity,
  authority generation/descriptor digest and opaque record IDs while replacing
  the private artifact path and retaining no bytes or passphrase.
- Post-run runtime inspection: workspace `.venv/Scripts/aeat.exe`, package
  `cadrumo==0.5.1`, authority generation
  `065049eb22e4a46f70281b940b5ce9ffeb2564adce39e050665d6fa370f21a98`,
  descriptor SHA-256
  `fe73492dbafb69e899833b88f2f70d1c25438115bde87d0ad867d4dac516c022`.
  Verify/export remain the next bounded acceptance action.
- Fresh-process verification now grants `verificado_completo`. Export is executed
  once and refuses exactly with `FAIL_MODELO_EXPORT`: Modelo 303 requires explicit
  AEAT product/software identity authority. The passing acceptance receipt is
  explicitly `verified_export_blocked`; it records no artifact, digest, parser
  success or exported result and marks canonical parsing
  `not_run_product_software_identity_pending`.
- The required authority is an AEAT-assigned four-byte program identifier,
  validated nine-byte developer tax ID and reviewed evidence reference/digest.
  No public writer/CLI seam currently supplies it. Test literals `C303` and
  `Y0000001S`, taxpayer/presenter identity, provider cc and session UUID are not
  valid substitutes and were not used. Provider/cc/UUID remain pending exactly
  as the session brief records.
- Blocker-aware installed acceptance: 1 passed in 118.66s, log
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T191207.311466Z-pytest-19012-9c03b850/run.log`;
  targeted Ruff, formatting, basedpyright and diff checks passed. The preserved
  success branch will bind export receipt/digest/size, canonical parser verdict
  and exported `iva.resultado=10.50` once reviewed identity authority exists.
- Phase 5 TUI discovery (Luna Max, read-only): ledger classification uses the
  injected shared `ManualLedgerTransactionPatch` submitter; the former screen
  offered business classification alone. Canonical invoice lines already belong
  to `build_catalogue_invoice`, while TUI invoice DTO/form/door still carry only
  scalar inputs. TUI M303 calculation request still lacks ordinary secure
  attestation/options; its shared operation and lifecycle files are peer-dirty.
- Bounded TUI classification candidate now exposes explicit IVA base/rate/tax,
  category, deduction kind, business percentage, usage ratio and prorrata
  reference through the existing patch/door, omitting blank fields and refusing
  invalid entries before write. The shared worktree concurrently acquired an
  `irpf_category` field in the same file from an unidentified peer; preserve it
  and coordinate ownership before staging/committing the combined file.
- Corrected focused integration selection `-m integration` passed 26 tests after
  DTO/focus assertions were updated; log:
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T195030.624644Z-pytest-68912-5e1f4912/run.log`.
  This predates the pending four-locale copy wiring; rerun focused tests and
  targeted Ruff/basedpyright/diff after catalogue changes. No broad gate is
  reserved or run for this slice.
- Locale owner is preparing 11 canonical `tui.ledger.classification.*` keys in
  en/es/ca/hu via `dev.locales set-batch`; no direct catalogue edits. Next
  safe slice after classification is repeated invoice-line TUI capture through
  the existing shared writer, with readback requiring coordinated shared
  projection ownership. Export stays blocked by genuine product identity.
- Locale authoring completed through `uv run --no-sync python -m dev.locales
  set-batch` for all four `common.yml` catalogues; its canonical agenda
  reflow/reordering retains the same values. The explicit temporary manifest
  was removed. Screen copy now uses those keys; it no longer imports the
  calculation registry. Deduction membership is checked by the shared patch
  model, while category membership remains a downstream shared authority
  concern, not a TUI-side calculation.
- Final classification-owned gate: 26 focused integration tests passed, log
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T195843.092958Z-pytest-37960-370ab757/run.log`;
  targeted Ruff format/check, basedpyright (zero errors/warnings/notes) and
  scoped diff check passed. No persistent process remains. The broader ledger
  workspace sweep separately fails its no-calculation-import assertion because
  peer-dirty `invoice_entry.py`, `actividad_asset.py`, and
  `models_actividad_asset.py` import domain calculation registry modules;
  this classification slice does not import them. Coordinate that failure
  with their owners, do not weaken the boundary test.
- Classification, its two focused tests and the four locale catalogues remain
  uncommitted in the shared worktree. An unrelated concurrent `irpf_category`
  addition landed in `classification.py` during verification; commit ownership
  of that combined file is pending coordination. New peer invoice files are
  also in flight; do not overlap them.
- Decision-critical review caveat: screen-local `IvaCategory(category)` establishes
  only nonempty token shape, not published-category membership. The prior
  direct registry lookup broke the TUI no-calculation-import boundary. Before
  treating the classification slice as fully accepted, coordinate a shared
  application/domain validation owner and prove an unknown category cannot
  persist into an apparently complete return; do not reintroduce calculation
  imports into the screen. The concurrent invoice-entry edit likewise uses
  `IvaCategory(...)`, so a common owner matters more than per-screen fixes.
- Luna Max traced the gap: invoice builder validates category membership through
  `Invoice` payload normalization, but the public manual-ledger transaction
  patch persists an opaque nonempty `IvaCategory` without membership validation.
  In-scope IVA aggregation later uses the registry's `.require()` and does not
  produce a normal complete observation for an unknown token (outer refusal
  projection NOT RUN). `application/ledger/actions_manual.py` with its existing
  pinned `LedgerActionPorts` is the narrow shared, date-aware write seam;
  coordinate income/assets owners before touching it. Regressions NOT RUN:
  unknown add/classify refusing without catalogue/event mutation, valid dated
  transaction/invoice tokens, legacy invalid in-scope calculation refusal, and
  out-of-scope/excluded controls. No second registry or TUI-side check.

## 2026-09-21 continuation after user instruction (baseline 135d6c116a)

- User explicitly directed commit-first integration while preserving collisions.
  Combined IVA/income TUI classification, tests and four locale catalogues were
  committed on `tui/modelo` as `c33e3e48f6`; this preserved the peer-added
  `irpf_category` field and did not stage peer invoice/assets changes. Exact
  post-commit focused integration command
  `uv run --no-sync pytest -q -n0 -m integration
  src/cadrumo/entrypoints/tui/ledger/tests/test_ledger_classification_iva.py
  src/cadrumo/entrypoints/tui/ledger/tests/test_ledger_flows.py` passed 26/26;
  log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T210643.753336Z-pytest-76408-b17711ff/run.log`.
- The broader ledger boundary gate's exact invariant is no CLI, adapter or
  `domain.calculations` imports inside the TUI ledger screen package. The
  remaining imports are in committed assets-owned `actividad_asset.py` and
  `models_actividad_asset.py`; this is a real assets integration dependency,
  not an IVA classification regression. Income handoff identifies concurrent
  owner for dirty invoice entry/ledger door changes. Do not weaken the test.
- Luna Max export trace: the 2025 DP30300 official design has a four-character
  `Versión del Programa` at 93-96 and developer NIF at 101-109. Official Note 1
  says the development entity fills both; it does not state AEAT assignment.
  The accepted export ADR already requires explicit product authority, so it
  was reused unchanged. The stronger incorrect `AEAT-assigned` docstring was
  corrected in `domain/filing/software_identity.py` and committed as
  `fcba11eb2b`; targeted Ruff/format/diff checks passed. `PACKAGE_VERSION`
  handling for M100 is separate and its 3-byte `051` cannot fill M303's
  4-byte field. A genuine approved release identifier or derivation, developer
  NIF, and reviewed evidence reference/digest are still missing; user asked
  asynchronously for the exact values/approver. No identity was invented.
- Luna Max verification audit: `verificado_completo` is a calculation/evidence
  grant, not export readiness; CLI and IVA acceptance already report
  `verified_export_blocked` separately. TUI file affordance may show a report
  ID without checking grant, but the export authority still refuses; its
  lifecycle/workbench owners are peer-dirty. Proposed TUI affordance correction
  is pending owner coordination; no verification downgrade.
- Leased writer implementation now in progress with Terra High: only
  `application/ledger/actions_manual.py` and focused application-ledger tests.
  It will use `require_iva_category(category,
  effective_date=command.booked_date, authority=ports.operation)` before
  create/update persistence, preserving declared tokens and batch atomicity.
  Exact reserved test: `uv run --no-sync pytest -q -n0
  src/cadrumo/application/ledger/tests/test_manual_iva_category_membership.py`;
  result pending. No full lane reserved.
- One Terra Max owns a new installed IVA TUI-only capture/classification and
  fresh-process reopen acceptance test under `dev/acceptance/iva/`; its focused
  installed lane is reserved exclusively, result pending. No M303 calculation
  or export claim from that slice. Luna Max is tracing the public product
  identity injection/evidence seam while values remain externally pending.
- Shared ledger validation delivered as `9865586749`: `actions_manual.py`
  checks typed category membership through the pinned authority at booked date
  before create and shared update persistence. `None` remains unset;
  registry-declared `unknown`, `operacion_no_sujeta`/`domestic_not_subject` and
  `erroneous_invoice` are not remapped or treated as declarable. Real-authority
  focused tests passed 5/5 (final log
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T211612.310031Z-pytest-752-b9eeaa6b/run.log`);
  targeted Ruff/format/basedpyright/diff passed. Two existing integrated
  handoff nodes (270-row bulk save-once and CLI update load-once) passed 2/2,
  log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T211744.150068Z-pytest-30552-7630a09f/run.log`.
  Batch preserves existing partial-success semantics: one valid row persists
  once, invalid later row remains unchanged and appears as a failure. No
  aggregation defense was removed.
- User clarified they are Cadrumo's developer but are not official/approved and
  these EEDD header fields are not fillable by Cadrumo. Luna Max found no
  product-level secure enrollment owner and no official/accepted authority for
  a blank non-EEDD substitute. The accepted registry audit
  `.vault/audit/2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit.md`
  at 9268-9289 says EEDD-delegated positions must not be authored as registry
  values; their emission remains a product-authority question. Therefore do
  not add a CLI identity injection, fabricate values, emit blanks, or call
  M303 export accepted. Retain the exact installed export refusal. An
  independently valid non-EEDD path would require new official evidence and
  an accepted authority decision.
- Luna Max selected an independent installed 2025/1T multi-rate case. The
  accepted runner/test were committed as `848c1a3a1b` in
  `dev/acceptance/iva/multirate_cli_journey.py` and its focused test. One
  reserved installed check passed (synchronous process exit 0, 30.3 s; pytest
  emitted no log/retained receipt). Fresh-process readback preserved an issued
  invoice's RATE_21 and RATE_10 lines and both transaction links. Independent
  oracle observations were 21.00 + 5.00 - 10.50 = 15.50; verification granted.
  Export was explicitly not attempted because product identity is unavailable.
  Source identity `b8c3da0383f4d58cc649d29bf2c3b35b63b09ee3`, package
  `cadrumo==0.5.1`, authority generation
  `db354561492ec6670dc775f9dd7fa24526098b74ab6b86dac0d5134df16430b4`,
  descriptor SHA `a4c77146a93ba2c2ad1e293a3330e420dcba999113da924fda122dbff9dc571b`.
- TUI installed capture/classification child was proven through site-packages:
  synthetic statement import and both combined classification forms completed;
  no invoice/link/M303 action was taken. Fresh-process Ledger readback remains
  unproven. Two reserved tests failed only at reopen; latest log
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T214230.004555Z-pytest-49220-cf668ca0/run.log`
  (handle 99824, exit 1). A final diagnostic rerun at
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T214652.536966Z-pytest-32152-6bbab707/run.log`
  (handle 18988, exit 1) preserved `stage=launcher_not_entered` in the
  sanitized reopen receipt. The second installed `launcher.main()` returned
  before `admitted_session_autopilot` invoked `drive_after_home`; it never
  reached Ledger/Entries. This is not evidence of a product persistence defect.
  The shared installed-session helper boundary is
  `dev/acceptance/income_tax/installed_tui_child.py`; income/launcher owner
  coordination is needed for a narrow second-session admission check. The IVA
  harness files remain untracked and failing, owned by the bounded TUI worker;
  do not stage them as passing acceptance or assert TUI persistence or
  cross-frontend continuation from capture-only evidence.
- Luna Max traced the second-session admission branch: headless installed
  sessions offer no credential journey (`entrypoints/tui/installed_session.py`
  355-379), and a fresh process without a resumable session can exit locally
  with `CREDENTIALS_REQUIRED` before the autopilot callback (application
  `user_profile/session_admission.py` 166-194). This is a plausible cause,
  not proven by the sanitized receipt; the exact admission outcome was not
  retained. The shared helper is clean but the launcher is peer-dirty, so
  coordinate the owner before changing it. The IVA harness was committed as
  `316eb538c1` with its integration node explicitly skipped pending admission
  (not xfail or passed). Exact narrow check yielded `1 skipped`, log
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T215906.139149Z-pytest-42372-49112746/run.log`.
- Luna Max identified an independent identity-free 2025/4T negative-result
  case: one deductible purchase IVA 10.50, no sale, local
  `work file --refund-election compensar`, followed by fresh-process
  `app live iva-wallet history` for generated/available credit and carry lot.
  Its `work file` is a local state transition with `aeat_accepted=False`,
  not AEAT submission. The first reserved installed attempt refused at 4T
  calculation with `ERROR_MODELO_IVA_WALLET_RECONCILIATION_BLOCKED` because
  the fixture lacked the applicable 3T observation (handle 65708; log
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T220659.132687Z-pytest-21008-b9dd60c6/run.log`).
  Seeding a synthetic zero 3T recurrence satisfied that gate. The next run
  reached fresh wallet readback but a test expecting only one row refused,
  because the 3T seed correctly remained visible (handle 11833; log
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T220904.896973Z-pytest-57112-ee5983fe/run.log`).
  The final narrow assertion preserves both rows: 3T `operator_seed` zero and
  4T `app_filing` generated/available 10.50, plus one 4T remaining lot 10.50.
  Exact installed node passed 1/1 (handle 81093; log
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T221237.280041Z-pytest-49096-1bad1831/run.log`), and Ruff,
  format, ty, whitespace checks passed. The owned driver/test were committed
  `ee52da4a2b`. Because a post-pass integer type guard entered that commit,
  the exact installed node was reserved and rerun on committed source
  `ee52da4a2b95d8debe767d88c2eae8c2f7c8c3e4`: 1 passed, exit 0, log
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T221624.849106Z-pytest-21976-b35ac94f/run.log`.
  This proves local pending compensation history, not external
  confirmation, refund approval/payment, annual reconciliation, or export.
- Refund-election contrast is a bounded unstaged diff in only the same two
  `negative_4t_cli_journey.py`/test files. It parameterizes the local election
  and expects a fresh 2025/4T `devolver` filing to retain no generated carry
  or lot. The public contract labels this an election only: local pending
  settlement remains `NOT_REQUESTED`, with no approved/paid claim.
  Ruff/format/ty/diff passed. One reserved serial two-node check retained
  compensar PASS, but devolver failed before calculation at synthetic
  `app ledger invoice add` with `INTERNAL_CLI_UNEXPECTED_BOUNDARY`; log
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T222406.397163Z-pytest-38880-64a092be/run.log`.
  Read-only failed-store diagnostics locate an unbound
  `profile_custody_port` invariant through profile-summary/catalogue-port
  resolution; a nested SyntaxError/FileNotFoundError leaves the antecedent
  uncertain. Luna Max is tracing the precise composition owner and check.
  Do not stage the failing refund test as accepted, infer a refund request, or
  mutate profile-owned code without coordination. Installed package remains
  `cadrumo==0.5.1`, authority generation `db354561492ec6670dc775f9dd7fa24526098b74ab6b86dac0d5134df16430b4`.
- An isolated unchanged `devolver` rerun failed even earlier at profile
  creation: empty child stdout caused `JSONDecodeError` after about 30s, with
  no persisted profile bucket. Log
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T223622.485473Z-pytest-54860-c3e6a521/run.log`.
  Luna Max found `.venv/Lib/site-packages/_editable_impl_cadrumo.pth` points
  to live `src` twice and distribution `direct_url.json` says editable. Thus
  the prior `.venv/Scripts/aeat.exe` is an installed console script but imports
  mutable checkout code; `cadrumo==0.5.1` alone did not pin product bytes.
  Source churn could explain the SyntaxError/FileNotFoundError and unstable
  early failures, but causation is NOT PROVEN. No timeout, OS termination,
  path collision, or inherited CADRUMO_* contamination was evidenced.
- Root CLI composition source already binds custody through
  `profile_adapter_composition()` and `composed_profile_persistence_ports()`;
  current invoice factory does not itself call the profile-summary edge in the
  failed trace. The fix at `072b643fd44` is present; do not patch invoice or
  custody code from that ambiguous editable-runtime exception.
- The supported real-wheel client fixture is already owned in
  `dev/packaging/release_cohort_support.py::client_venv_template` and used by
  IVA TUI. A bounded worker changed only IVA CLI acceptance test binding
  (new test fixture + three test modules) to that wheel console script,
  preserving the unstaged refund diff and fresh stores. Ruff/format/ty/diff
  pass. The exact serial four-node real-wheel check ran under PID 76512; log
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T224625.672911Z-pytest-76512-eacd426b/run.log`:
  ordinary M303 PASS, 2025/4T compensar PASS, 2025/4T local devolver PASS;
  multirate FAIL at `app modelo work calculate` with
  `ERROR_FINANCIAL_AGGREGATION_VALIDATION` (bucket-derived bindings conflict
  with supplied input). Luna Max traced that multirate conflict to the
  contradictory synthetic transaction category below.
  The worker's first 30-second tool yield was not process completion; final
  exit was 1 at 22:52:56 UTC. Wheel payload digest was computed/validated by
  the shared fixture but not retained in a sanitized receipt, so do not invent
  a digest or relabel old editable receipts as wheel receipts.
- Luna Max found the multirate fixture's 10% sale transaction was tagged
  `domestic_general` while its linked invoice RATE_10 line derived
  `domestic_reduced`. The invoice-vs-ledger silence guard was right to refuse
  this contradiction; no aggregation code changed. The fixture now uses
  explicit `domestic_general` for 21% and `domestic_reduced` for 10%.
  One exact real-wheel multirate rerun passed 1/1 (session 91381, exit 0,
  125.22s; log
  `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T230053.950203Z-pytest-11180-3275ba4b/run.log`).
  Independent oracle: general 21.00 + reduced 5.00 - deductible 10.50 =
  `iva.resultado` 15.50; verification complete. The wheel-bound ordinary,
  compensar, and local devolver nodes had passed unchanged in the preceding
  serial run. Ruff, format, ty and diff checks passed on all six touched
  files. Wheel fixture + refund contrast + corrected multirate fixture were
  committed as `2a58781fb1`. The test receipts remain in-memory and the
  wheel payload digest is NOT retained, so claim only the observed run/log
  identities, not a retrospectively invented artifact digest.
- Annual 390 read-only candidate: existing `docs/_sequences/how-to/modelo-390/
  modelo-390-annual-2025.json` frames 25-27 have a 2025/0A ordinary-regime
  chain over four locally filed 303 periods. Independent oracle accrued
  1,470.00, deductible 105.00, result 1,365.00; local-chain advisory is not
  official filing evidence. Installed wheel replay through calculate/verify is
  NOT RUN and should wait for runtime binding stability; no export identity is
  needed for calculation/verification.
## 2026-09-22 annual reservations

- Owner IVA root: exact focused regression `uv run --no-sync pytest -q -n0 -m unit src/cadrumo/adapters/persistence/profile/tests/test_iva_compensation_relation_prefill.py::test_modelo_390_partition_refuses_missing_intermediate_m303_periods`; first run expected to fail before resolver correction. No aggregate lane reserved.
- Owner Terra annual-1T: exact installed-wheel node `uv run --no-sync pytest -q -n0 -m integration dev/acceptance/iva/tests/test_annual_cli_journey.py::test_installed_cli_2025_1t_local_filing_establishes_annual_foundation`; pending first execution. Worker owns only the two new annual acceptance files.
- Luna history audit found the existing four-quarter source selector can be partially populated, while the resolver currently resolves from any nonempty subset. The chosen regression uses valid 1T and 4T observations, missing 2T/3T, and expects both annual compensation bindings unresolved with typed evidence diagnostics. Product owner is IVA application calculations; this is not an invented universal filing-history dependency.
- The focused regression failed before the fix (one failure, `20260921T231503.003966Z-pytest-58824-6e2e0e26/run.log`): the 1T/4T subset resolved the last-period binding to 150.00. Gating the lower-level partition calculation itself broke three established partial-evidence validation tests (3 failed, 7 passed, `20260921T231617.833840Z-pytest-23972-2b97e862/run.log`). The final correction gates only the annual source resolver, preserving lower-level validation. The exact affected two-file selection passed 10 tests, exit 0, `20260921T231653.807850Z-pytest-70224-234f5bc7/run.log`; targeted Ruff, format, ty and diff checks passed. Reservation released.
- Terra annual-1T's first exact installed node was launched once; its supervising tool lost the terminal result while pytest PID 7884 later exited. Neither count nor receipt was recoverable, and no pass is claimed. Owner IVA root reserves one serial rerun of the same exact node after verifying the prior PID is gone; this will be monitored to final result.
- The serial rerun of `dev/acceptance/iva/tests/test_annual_cli_journey.py::test_installed_cli_2025_1t_local_filing_establishes_annual_foundation` passed 1, exit 0, in 229.13 s; log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T231816.333613Z-pytest-7876-afe3a662/run.log`, supervised session 32184 closed. The shared fixture installed a wheel. This proves 2025/1T calculate/verify, local pending filing and fresh-process work/filing-record readback; not AEAT confirmation, M390, or export. The prior unobserved run is not relabelled. Source state includes committed history fix `bf8e3d874c` and the two new uncommitted annual driver/test files at test time.
- Luna TUI admission delta at HEAD `9e05324019` found the fresh headless IVA reopen exits before callback because no process-local session or acceleration receipt exists and headless disables credentials; `CREDENTIALS_REQUIRED` is an admission/setup gap, not proof of persistence loss. The peer income continuation harness uses the production Login screen to admit first. Terra IVA TUI now owns only `dev/acceptance/iva/installed_tui_capture_reopen.py` and its focused test, adds the production Login screen in the fresh reopen child, and removes the stale skip. Ruff/format/diff checks pass; targeted ty has four pre-existing redundant-cast diagnostics in the owned driver, to address after runtime test. Owner IVA root reserves exactly `uv run --no-sync pytest -q -n0 -m integration dev/acceptance/iva/tests/test_installed_tui_capture_reopen.py::test_installed_tui_captures_classifies_and_reopens_ordinary_iva_rows`; pending execution, no full lane.
- The reserved installed TUI node exited 1, 1 failed in 131.41 s, log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T232949.894997Z-pytest-40688-165d14f3/run.log`. Fresh-process production Login admission passed the former `launcher_not_entered` point; the first failure is now `_readback_canonical_fields` at driver line 825, reporting a submitted IVA field mismatch in the installed public ledger view. This is not TUI acceptance. Terra IVA TUI owns a bounded field-specific diagnosis and a new exact rerun proposal; product correction, if needed, requires its owner. Reservation released.
- Terra annual four-quarter M390 worker preserved the committed 1T driver and added a separate installed-wheel scenario using the existing docs runner's canonical generated synthetic filing evidence. Targeted Ruff/format/ty/diff checks passed; no installed four-quarter run yet. Owner IVA root reserves exactly `uv run --no-sync pytest -q -n0 -m integration dev/acceptance/iva/tests/test_annual_cli_journey.py::test_installed_cli_four_local_303_quarters_verify_2025_m390`; no full lane or export.
- The first exact four-quarter installed node exited 1, 1 failed in 91.83 s, log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T233345.236700Z-pytest-73480-c2dbb488/run.log`: the first 303 `work calculate` rejected harness option `--m303-filing-evidence` as unknown. This is a public-command mismatch before annual calculation, not an M390 verdict. Terra annual owner is tracing the supported syntax and will propose a narrow rerun; reservation released.
- TUI installed failure was narrowed to `taxable_base` text presentation, not lost persistence: public ledger view normalizes Decimal `100.00` to `100`, matching existing CLI UX tests. Terra TUI now normalizes expected decimal text independently, preserves values and checks, adds only the field name to sanitized mismatch errors, and removed four pre-existing redundant casts. Targeted Ruff/format/ty/diff checks pass. Owner IVA root reserves the same exact installed TUI node once more after this harness-only correction; pending execution.
- The corrected installed TUI node passed 1, exit 0, in 86.24 s, log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T233544.171909Z-pytest-39596-5667549f/run.log`. It proves installed TUI ledger capture/classification, production Login admission in a fresh reopen child, and canonical public ledger readback. It does not prove TUI invoice capture, Modelo 303 calculate/verify, TUI-only full journey, or export. Reservation released.
- Annual CLI mismatch traced: installed `work calculate --help` and source `_modelo_work_calculate_cli.py` accept exoneration attachment ID/SHA, not `--m303-filing-evidence`; public `attest-m303-exonerado-390` is the supported authority. Terra annual driver now attests each quarter and passes supported attachment options; 1T API retained, static Ruff/format/ty/diff pass. The docs annual sequence still has a stale `--m303-filing-evidence` frame at `docs/_sequences/how-to/modelo-390/modelo-390-annual-2025.json:419` and later quarters; separate docs owner correction pending, not silently rewritten here. Owner IVA root reserves one rerun of `uv run --no-sync pytest -q -n0 -m integration dev/acceptance/iva/tests/test_annual_cli_journey.py::test_installed_cli_four_local_303_quarters_verify_2025_m390`; pending.
- Corrected installed four-quarter/M390 node passed 1, exit 0, in 285.46 s, log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T234004.973520Z-pytest-74876-4a88bebe/run.log`, supervised session 43997 closed. The test asserts four distinct local/pending 303 records and fresh-process binding, 2025/0A M390 calculate/verify, independent annual oracle devengada 1,470.00 / deducible 105.00 / resultado 1,365.00. No AEAT confirmation or export. Reservation released. The 1T foundation path was refactored into shared driver helpers during this addition; its earlier pass belongs to the pre-refactor source. A new exact 1T regression is reserved before claiming the combined driver stable: `uv run --no-sync pytest -q -n0 -m integration dev/acceptance/iva/tests/test_annual_cli_journey.py::test_installed_cli_2025_1t_local_filing_establishes_annual_foundation`.
- The post-refactor exact 1T installed-wheel regression passed 1, exit 0, in 124.88 s, log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-21/20260921T234543.668774Z-pytest-17064-c54fe08a/run.log`, supervised session 91987 closed. Source commit `17e2f0441b` contains the four-quarter extension and shared helper refactor. Both annual installed nodes are now passing on their respective documented source states; no export is claimed. Reservation released.
- Luna TUI invoice/Modelo audit at HEAD `c3f86dc06e` (read-only): installed TUI invoice entry remains scalar, single-line (`ledger/invoice_entry.py`, `ledger/models.py`, `ledger_doors.py`); full multi-line TUI financial capture is not proven and requires the shared request/editor owner. Canonical invoice-to-transaction link is wired through the reconciliation screen/launcher. Modelo overview exposes calculate/verify through the shared lifecycle door. Terra IVA TUI Modelo continuation owns only new `dev/acceptance/iva/installed_tui_modelo_journey.py` and its new focused test, aiming for installed CLI-to-TUI 2025/1T calculate/verify with the independent 10.50 oracle. No test reserved or run yet; not TUI-only capture.
- The proposed installed CLI-to-TUI 303 calculate driver was stopped before execution and its two untracked draft files were removed by their sole owner, with no peer edits. Luna independently confirmed at HEAD `c3f86dc06e`: TUI lifecycle sends only work ID/actor; shared operation request/executor accepts only those; `calculation_actions` accepts ordinary-M303 filing evidence optionally, while `revision_persistence` refuses M303 without it. CLI calculate/quickfile alone author the four explicit joint-return, annual-volume, attestation ID/SHA inputs. The TUI manual edit UI is only casillas/bindings; no supported draft-preparation path persists these inputs. This is a product/shared-operation gap, not a harness defect. Exact owner deliverable: extend the existing shared typed Modelo calculate input/evidence contract and current TUI workspace to collect the four fields with existing attestation integrity, preserving one calculator/persistence owner; do not add a TUI-only calculator or bypass persistence. Proposed checks NOT RUN: incomplete evidence refuses before revision persistence; CLI and TUI equivalent payloads persist equivalent facts; installed CLI-prepared draft → fresh installed TUI calculate/verify → fresh public readback with 10.50 oracle. TUI multi-line invoice editing remains a separate owner dependency. No TUI Modelo acceptance is claimed.
- One Sol High architecture adviser reviewed this unresolved shared-operation choice without coding/tests. Favored option is extending `ModeloWorkCalculateRequest` with an explicit typed ordinary-M303 evidence subrequest and reusing existing authoring/calculation, with secure request custody; alternatives are a separate M303 registered operation or a secure interaction after submission. The favored path changes all-model request storage policy, registration fingerprint and composition ports, so it is NOT an owner-approved implementation decision. Accepted coverage to inspect before work: IVA M303 evidence-authoring ADR, form/semantic dual-keying ADR, TUI architecture secure-custody ADR, and operation-observation versioning/non-retention decision. Current `application/modelo/operation_definitions.py` and `entrypoints/tui/modelo/lifecycle.py` are peer-dirty; do not edit or commit their unowned state without a coordinated file lease/owner-applied patch. Named decision requested of the shared Modelo/TUI lifecycle owner: choose the secure typed extension vs narrowly separate operation, then own registry/schema migration and focused parity/refusal tests. Export identity remains independently blocked by unavailable approved developer release fields.
## 2026-09-22 disjoint IVA continuation after LEDGER-01 lease

- Ledger release is prepared in `handoffs/2026-09-22-iva-ledger-release.md` (commit `b240a2a319`). Coordinator delivery and Ledger acknowledgement are both pending; no overlapping edits or active IVA process handles. This is not an income/TUI reservation transfer.
- Four-input ordinary-M303 evidence table and minimal shared-operation proposal are prepared in `handoffs/2026-09-22-iva-modelo-evidence-contract.md` (commit `2374746b35`), addressed to the income/shared Modelo-TUI owner. Direct session delivery, owner decision and file lease remain pending. No operation or TUI file was edited.
- Luna identified a clean, disjoint V6/V8 gap: a replacement local 303 should supersede lifecycle metadata without mutating the retired filing's settlement/credit snapshot. Terra added one focused test only in `src/cadrumo/adapters/persistence/profile/tests/test_iva_wallet_engine_filing.py`; static Ruff, basedpyright, compileall and diff checks passed. Owner IVA root reserves exactly `uv run --no-sync pytest -q -n0 -m unit src/cadrumo/adapters/persistence/profile/tests/test_iva_wallet_engine_filing.py::test_refiling_local_modelo_303_preserves_each_settlement_credit_snapshot_and_lifecycle`; NOT RUN before this reservation, no aggregate lane.
- The exact replacement-local-303 snapshot regression passed 1, exit 0, in 13.44 s, log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-22/20260922T005246.055004Z-pytest-24776-aaf901a4/run.log`. It proves immutable retired/current local settlement and credit snapshots plus lifecycle supersession, not installed AEAT evidence. Reservation released; no product or Ledger-leased file changed.
- Annual docs sequence source `docs/_sequences/seeds/iva-year-2025.seq` is clean. The four stale `--m303-filing-evidence` steps must be replaced with supported public attestation plus explicit false/false and attachment ID/SHA. The three JSON goldens are CLI-owned; only the sequence refresh command may regenerate them. Terra docs owns seed and affected three goldens pending exact refresh reservation.
- Annual docs seed correction committed as `a805853c4c`: four public attestations with captured ID/SHA and explicit false/false calculations replace the unsupported flag. Parser discovery and diff check passed; generated goldens remain untouched. Owner IVA root reserves serial exact commands for the clean `how-to/modelo-390` page: `uv run python -m dev.docs.sequences refresh --page how-to/modelo-390`, then `uv run python -m dev.docs.sequences check --page how-to/modelo-390`, then `uv run python -m dev.docs.sequences check --page how-to/modelo-390 --coherence`. The refresh may rewrite only CLI-owned goldens; review all diffs and retain failures honestly. No other docs page or test lane is reserved.
- First reserved page refresh terminated without a captured console/exit receipt; all observed child PIDs are closed. Generator wrote only `modelo-390-annual-2025.json` and `modelo-390-supply-binding.json`; `modelo-390-inspect.json` remains stale with the unsupported flag. Do not accept or commit partial generated output. Static discovery found all 11 page sequences, so an inspect-specific `SequenceEngineError` is plausible but unproven. Owner IVA root reserves one diagnostic `uv run python -m dev.docs.sequences check --sequence modelo-390-inspect` to surface the exact failure; this single-sequence check is diagnostic only, not the page gate. The earlier page check/coherence reservations remain queued and must wait for complete generation.
- The exact inspect diagnostic ended exit 1 (supervised session 33473 closed) at inspect sequence line 18: public `aeat --format json app modelo iva-wallet balance --as-of-year 2025` returned `FAIL_IVA_COMPENSATION_HISTORY_PERSISTENCE`, cause `ValidationError`, operation `list`, after four locally filed 303 periods. This is not an unsupported-option failure; the shared seed correction remains valid, but generated docs are incomplete. Two provisional changed goldens are uncommitted; the third remains stale. Page check/coherence stay queued, not run. Luna Max owns a bounded read-only persistence trace; no product or generated golden hand edit is authorized by this diagnosis.
- Luna Max found one clean directed V6/V7 boundary not already proved: a present filed intermediate quarter with explicit all-zero carry state must count as history, unlike a missing quarter. Existing missing/stale/wallet/replay nodes already have passing evidence and are not repeated. Terra IVA zero-history owns only `test_iva_compensation_relation_prefill.py`, adding one focused regression; exact run awaits reservation after static handoff.
- Terra IVA zero-history added one focused adjacent regression in the clean annual-partition test file, with canonical `NEGATIVA` for zero-result 2T/3T; targeted Ruff/format/diff checks passed. Owner IVA root reserves exactly `uv run --no-sync pytest -q -n0 -m unit src/cadrumo/adapters/persistence/profile/tests/test_iva_compensation_relation_prefill.py::test_modelo_390_partition_accepts_explicit_zero_intermediate_m303_periods`; NOT RUN before this reservation. No aggregate lane.
- The first exact zero-history node passed 1, exit 0, in 5.23 s (`20260922T010159.858632Z-pytest-63776-423e4fd3/run.log`), but lead review found its 1T credit followed by all-zero 2T/3T and 4T prior-credit representation economically inconsistent. This is a harness fixture issue, not accepted financial-chain proof. Terra is refining the same test to a coherent 1T–3T zero filing chain and 4T generated credit before a new reserved rerun. Do not cite the first pass as V6/V7 acceptance.
- The corrected fixture now has explicit all-zero `NEGATIVA` 1T–3T and a 4T `COMPENSACION` generating 50.00 with no prior carry; expected annual box 97=50.00 and box 662=0.00. Ruff/format/diff passed. Owner IVA root reserves one rerun of the same exact `uv run --no-sync pytest -q -n0 -m unit src/cadrumo/adapters/persistence/profile/tests/test_iva_compensation_relation_prefill.py::test_modelo_390_partition_accepts_explicit_zero_intermediate_m303_periods`; not yet run on corrected fixture.
- The coherent zero-history rerun passed 1, exit 0, in 6.05 s, log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-22/20260922T010252.559146Z-pytest-70392-c7deeb54/run.log`. It resolves annual box 97=50.00 / box 662=0.00 without missing-evidence diagnostics; the missing-quarter and stale-quarter passing evidence is reused unchanged. Reservation released.
- Luna's bounded docs-inspect trace identified a likely independent IVA persistence defect: `IvaCompensationHistoryRepository.load_period` and `list_periods` decode stored APP_FILING rows before entering the bundled governed authority scope, while the persisted `SubjectTaxId` validator requires that scope. The exact docs inspect check failed with `FAIL_IVA_COMPENSATION_HISTORY_PERSISTENCE`/`ValidationError`; no raw taxpayer data was logged. Terra owns only the clean history adapter and its provenance-roundtrip test, with a new 2025 APP_FILING save→list/load regression now added while the adapter remains unchanged. Ruff/format passed. Owner IVA root reserves exact pre-fix node `uv run --no-sync pytest -q -n0 -m unit src/cadrumo/adapters/persistence/profile/tests/test_iva_compensation_provenance_roundtrip.py::test_app_filing_history_round_trips_through_list_and_load_under_a_bundled_authority_scope`; NOT RUN before this reservation. Adapter fix and docs refresh wait for result.
- First reserved pre-fix history node exited 1, but failed at `NO_ACTIVE_SESSION` because its fresh `Context()` also removed the secure storage session, before reaching the intended tax-ID decode; log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-22/20260922T011546.223584Z-pytest-38472-5470598f/run.log`. This is a test-isolation error, not evidence for the proposed adapter cause. Terra is refining the test to remove only the ambient governed-facts scope while preserving the secure runtime; adapter remains unchanged. No product fix/test claim yet.
- The corrected test-only isolation clears `_VALIDATING_GOVERNED_FACTS` with a restored token while retaining the secure runtime session. Targeted Ruff/format/diff pass; adapter still unchanged. Owner IVA root reserves one pre-fix rerun of the same exact `uv run --no-sync pytest -q -n0 -m unit src/cadrumo/adapters/persistence/profile/tests/test_iva_compensation_provenance_roundtrip.py::test_app_filing_history_round_trips_through_list_and_load_under_a_bundled_authority_scope`; pending.
- Corrected pre-fix history node exited 1 as intended, log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-22/20260922T011713.083723Z-pytest-66672-25e642dc/run.log`: encrypted `Envelope[IvaCompensationPeriodState]` decode rejected `payload.taxpayer_nif` because no governed-facts authority was in scope, then adapter wrapped the Pydantic `ValidationError`. Secure runtime remained active, so this isolates the read-scope defect. Terra now applies the minimal adapter scope correction in the two owned clean files; post-fix node NOT RUN.
- Minimal history adapter correction now wraps both `self.load()` and `self.iter_records()` plus their coordinate confirmation in the existing bundled indexed authority operation; `_call_storage` error translation is unchanged. Only adapter and focused provenance-roundtrip test changed, targeted Ruff/format/diff passed. Owner IVA root reserves exact affected eight-test selection `uv run --no-sync pytest -q -n0 -m unit src/cadrumo/adapters/persistence/profile/tests/test_iva_compensation_provenance_roundtrip.py`; pending, no full lane.
- The affected provenance-roundtrip file passed 11 parametrized cases, exit 0, in 1.40 s, log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-22/20260922T011804.643785Z-pytest-76580-f5e53792/run.log`; the new APP_FILING save→list/load under absent ambient authority is green. Targeted ty also passed. Owner IVA root reserves exact adjacent adapter file `uv run --no-sync pytest -q -n0 -m unit src/cadrumo/adapters/persistence/profile/tests/test_iva_compensation_history_repository.py`; not yet run. The docs inspect sequence will be retried only after adapter integration, without relabelling the earlier partial refresh.
- Adjacent history-repository file passed 3/3, exit 0, in 1.35 s, log `C:/Users/hello/AppData/Local/Temp/.logs/test-runs/2026-09-22/20260922T011833.687751Z-pytest-42160-21798db4/run.log`. Product diff is limited to entering the established bundled authority operation before encrypted `load`/`iter_records` and retaining coordinate confirmation inside that same scope; no schema, wrapper/error-code or product authority changes. Provenance roundtrip and adjacent repository reservations released. Pending: commit this fix, then retry the single inspect sequence and regenerate its CLI-owned golden only on a terminally successful execution.
- IVA history read-scope fix committed as `2b29400e41`; no Ledger-leased file touched. Owner IVA root reserves exactly `uv run python -m dev.docs.sequences refresh --sequence modelo-390-inspect` as the smallest generator-owned retry on the corrected source. This can rewrite only the inspect golden; page-level check/coherence stay queued until terminal result and diff review. No duplicate page refresh is active.
- The reserved inspect refresh exited 0 and rewrote only its generator-owned golden; the annual and supply-binding goldens were already rewritten by the earlier interrupted page refresh. All three generated files remain uncommitted and provisional. Structural inspection found zero nonzero-exit frames in annual (31 frames), inspect (41), and supply-binding (30). Owner IVA root then ran the reserved `uv run python -m dev.docs.sequences check --page how-to/modelo-390`; supervised process 42522 exited 1 with 109 divergences. The first is a changed content-addressed M303 exonerado-390 attachment digest despite fixed `--observed-at`; captured argv and derived calculation revision IDs subsequently differ. This is a reproducibility/golden-comparison failure, not a failed annual calculation or successful documentation gate. The `--coherence` check remains NOT RUN. Do not repeatedly refresh or commit the volatile generated goldens until their deterministic-input or centrally reviewed comparison contract is established. Ledger delivery and acknowledgement remain pending, independently of this docs issue.
- Luna traced the volatility to the docs test-profile fixture: the attestation hashes canonical profile witness including `content_digest`; the witness digest includes profile `updated_at`, and fixture upsert/replacement used direct `datetime.now(UTC)` outside the frozen clock. IVA root changed only those two profile-record timestamp writes to the canonical `_utc_now()` seam; session-open deadline continues to use real wall time. Static Ruff, format and diff checks passed. The reserved page refresh then exited 0, rewriting five generator-owned goldens; only annual, inspect and supply-binding changed in Git. Page check exited 0 (`cli-sequence goldens: clean`) and page `--coherence` exited 0 (`cli-sequence page coherence: clean`), including once-per-page seed reuse warnings. The fixture plus three generated goldens are committed as `96c6c4fb84`; no digest-masking policy was widened, no Ledger-leased file was touched. The prior failing check remains historical evidence, not a current pass.
- A new peer-authored `handoffs/2026-09-22-ledger-shared-file-return.md` is visible in the shared worktree and records LEDGER-01's acknowledgement of the published IVA release, integrated source `01b78c102116`, focused shared/IVA regressions and installed wheel identity. The file expressly says direct delivery to outside sessions is not claimed. IVA has not received a direct coordinator delivery/acknowledgement confirmation and has not edited or staged that peer handback. Treat the lease return as available for inspection, but coordinate the exact resumption boundary before editing shared files.
