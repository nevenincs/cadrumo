---
tags:
  - '#audit'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-repo-health-triage-adr]]'
  - '[[2026-06-04-repo-health-triage-research]]'
---

# `repo-health-triage` Code Review

## W01-001 | HIGH | Public Drive service injection bypassed credential-owned construction

Status: remediated.

The W01 resolver change added a public `drive_service` keyword to
`resolve_document_link`, allowing callers to bypass credential-owned Google Drive
service construction. This conflicted with the minimal-scope resolver posture and
converted the test monkeypatch repair into a production test-double injection
surface.

Remediation removed the public service keyword from `resolve_document_link` and
restored `_download_drive_file` to always construct the Drive service from
credentials. Focused download behavior is covered through the private
`_download_drive_file_from_service` helper instead of the public API.

## W01-002 | MEDIUM | Corpus provenance step overstated relative import conversion

Status: remediated.

The checked W01 plan row claimed the corpus provenance test had been converted to
a relative import, but `src/aeat/_data/corpus` is a data-tree test location with
no package context. Turning the data tree into a package just to satisfy the row
would risk changing package-resource behavior.

Remediation updated the S03 plan action through `vaultspec-core vault plan step edit`
to describe the implemented behavior: remove the AST-visible absolute self-import
through the established `aeat.core.resources` boundary.

## W01-003 | LOW | Phase summaries lacked scoped command-output evidence

Status: remediated.

The W01 phase summaries listed verification commands but did not preserve concise
exit-code and result evidence, despite the ADR requiring scoped command output.

Remediation added focused evidence lines to the W01 phase summaries and corrected
the S10 step record to describe the post-review resolver contract.

## W02-001 | INFO | W02 type-control review found no actionable defects

Status: verified.

The W02 review found no findings and no remaining HIGH or CRITICAL issue. The
review checked the centralized counterpart source-kind subset, typed secure
repository payload accessors, sanitizer parse-error narrowing, narrow
import-linter test-helper exceptions, and W02 plan/exec/audit evidence.

The reviewer noted one non-blocking residual edge: a manually constructed invalid
revision with retired `invoice` source can be silently skipped by the resolver,
but production registry validation rejects that source before resolver use and
current production registry data does not contain `source = "invoice"` entries.

## W03-001 | LOW | Parallel plan step closure left S24 unchecked

Status: remediated.

The W03.P07 review found that `W03.P07.S24` was still unchecked while matching
execution and index records existed for the step. The root cause was a local
workflow error: S24, S25, and S26 were closed in parallel, and concurrent writes
to the same plan file lost the S24 update.

Remediation reran the S24 plan-step closure serially, regenerated the feature
index, removed the stale plan template annotation block, and reran VaultSpec
checks successfully. No HIGH or CRITICAL findings were reported for the W03.P07
code changes. The reviewer noted no behavioral regression in CLI command
registration, storage-session fixture direction, or the `work calculate` typed
boundary extraction.

## W03-002 | CRITICAL | S35 used an unapproved diagnostics source package

Status: remediated.

The S35 diagnostics analyzer extraction was invalid because `aeat.diagnostics`
is not an approved hexagonal module and must not live under the production source
package. The earlier no-findings review is superseded by this architectural
boundary correction.

Remediation removed the `aeat.diagnostics` package, deleted its generated API
stubs, removed the stale Ruff exception, replaced live source references to the
unapproved module, and rewrote the S35 execution record to document the
emergency removal rather than the rejected analyzer extraction.

Validation confirmed that `aeat.diagnostics` no longer resolves through
`importlib.util.find_spec`, the exact source/docs/package reference search is
clean, Ruff and Ty passed on touched files, and the non-ledger affected pytest
slice passed. The ledger validation module still carries the unrelated
storage-route mismatch failure and was verified with collection only for this
emergency package removal.

Focused review by Cicero found no actionable findings and no remaining HIGH or
CRITICAL issues for the emergency removal. The reviewer confirmed the source
package and generated API pages are deleted, live `aeat.diagnostics` references
are gone from source/docs/project config, import discovery returns `None`, and
VaultSpec plan/exec/index/audit records are coherent for the corrected S35
scope.

## W03-003 | INFO | Formula initial-value extraction review found no defects

Status: verified.

The W03.P09.S31 review found no behavioral defect in the extraction. The runtime
keeps the same private call sites by importing `initial_values` and
`materialise_observations` under the old private helper names, while the new
module owns the previous-filing absent-by-design and projection guards.

Verification covered formula runtime behavior, Modelo 130 carry-forward
absent-by-design behavior, previous-filing smuggling/projection rejection, ruff,
the VaultSpec plan check, and the registry reviewability gate.

## W03-004 | INFO | Workbook parity complexity baseline review found no defects

Status: verified.

The W03.P09.S32 review found no behavioral defect because the slice deliberately
does not change workbook parity execution. `_workbook_parity.py` remains the
reviewed 1,336-line hotspot, and `test_registry_reviewability.py` now fails if
that module grows past the recorded baseline.

Verification covered the reviewability gate, focused workbook parity scan and
inventory behavior, and Ruff on the touched reviewability surface.

## W03-005 | INFO | Modelo binding-resolution extraction review found no defects

Status: verified with scoped residual.

The W03.P08.S27 review found no behavioral defect in the extraction. The
calculation action now delegates profile, borrador, relation, previous-filing
override, bound-casilla, and informational-period input assembly to
`_binding_resolution.py`; IVA wallet reconciliation remains in `_actions.py` for
the next dedicated slice.

Focused verification passed for profile binding, real profile binding, borrador
binding, previous-filing casilla override, declaration-period binding, and Ruff
on touched surfaces. A broader source-mesh calculation run still has two
pre-helper failures where Renta expense source resolution raises
`aggregation.renta_ledger.errors.invoice_bucket_mismatch` before binding
resolution is reached; that edge is outside this extraction and remains tracked
as a source-mesh preflight ordering issue.

## W03-006 | INFO | Modelo IVA wallet gate extraction review found no defects

Status: verified.

The W03.P08.S28 review found no behavioral defect in the extraction. The
calculation action now delegates Modelo 303 IVA wallet decision resolution,
binding application, persisted-decision replay checks, blocked-message rendering,
and taxpayer NIF lookup to `_iva_wallet_gate.py`, while preserving the existing
private `_actions.py` import surface used by export, CLI, and tests.

Focused verification passed for IVA wallet binding behavior, blocked-message
localisation, export refusal checks, the closure token, the IVA wallet engine
integration file, and Ruff on the touched action/gate/error-registry surfaces.
One attempted export pytest command used stale node ids and collected no tests;
the corrected export refusal node ids passed.

## W03-007 | INFO | Modelo revision-persistence extraction review found no defects

Status: verified.

The W03.P08.S29 review found no behavioral defect in the extraction. The
calculation action now delegates bucket-event emission, draft revision
persistence, calculation-created event emission, verified-complete filing
transitions, supersession state updates, filing-record writes, and work-unit
pointer advancement to `_revision_persistence.py`.

Focused verification passed for calculate idempotency, calculation-created
events, verify/file workflow gates, filing pointer updates, filing and
supersession events, Modelo 303 wallet pre-mutation refusal, and Ruff on the
touched action/persistence/test surfaces.

A dedicated `vaultspec-code-reviewer` delegation was attempted for this slice,
but the active subagent pool returned a thread-limit failure; the review was
completed locally against the mandatory code-review checklist.

## W03-008 | INFO | Ledger review projection extraction review found no defects

Status: verified.

The W03.P10.S33 review found no behavioral defect in the extraction.
`_actions.py` now keeps repository loading and delegates review filtering,
event-filter matching, row projection, and review-status classification to
`_review_projection.py`.

Focused verification passed for review period/status projection, direction
filtering, import/issue event filters, ledger list CLI filters, the full
application ledger action test file, and Ruff on the touched ledger surfaces.

## W03-009 | INFO | Ledger list CLI extraction review found no defects

Status: verified with scoped residual.

The W03.P10.S34 review found no behavioral defect in the extraction. The
`ledger list` command now delegates filter parsing, shared review-query
matching, group filtering, group ordering, paging, truncation footer
construction, row payload construction, and text-line rendering to
`_ledger_list.py`, while `_ledger.py` keeps Typer option wiring, repository
resolution, parse-error translation, and envelope emission.

Focused verification passed for list filters, cold-start no-profile refusal,
review-filter help wording, and Ruff on the touched ledger CLI surfaces. A
broader lifecycle CLI test currently fails before the list path on an unrelated
`ledger update` taxable-base plus IVA gross-validation refusal.

## W04-001 | INFO | Formulas dependency ownership review found no defects

Status: verified with scoped residual.

The W04.P12.S38 review found no behavioral defect in the dependency hygiene
decision. `formulas` remains declared for the workbook parity oracle, while the
production registry formula runtime remains import-free for the external
package. The Deptry `DEP002` exception is explicit and scoped to that ownership
decision rather than a blanket dependency suppression.

Focused verification confirmed that no Python import of the external `formulas`
package exists, `uv run --no-sync deptry .` no longer reports `formulas`, and
the VaultSpec repo-health plan validates. Deptry still reports planned residual
findings for `rich`, `torch`, `playwright_stealth`, and `prompt_toolkit`, which
remain open under W04.P12.S39-S42.

## W04-002 | INFO | Rich dependency ownership review found no defects

Status: verified with scoped residual.

The W04.P12.S39 review found no behavioral defect in the dependency hygiene
decision. `rich` is retained as a direct version pin for Typer's console
rendering path, while application code remains free of direct Rich imports. The
Deptry `DEP002` exception is scoped to that Typer ownership rather than a broad
unused-dependency allowlist.

Focused verification confirmed no Python import of `rich`, Typer metadata still
declares `rich>=13.8.0`, root CLI command materialisation succeeds, and
`uv run --no-sync deptry .` no longer reports `rich`. Deptry still reports
planned residual findings for `torch`, `playwright_stealth`, and
`prompt_toolkit`, which remain open under W04.P12.S40-S42.

## W04-003 | INFO | Torch runtime dependency removal review found no defects

Status: verified with scoped residual.

The W04.P12.S40 review found no behavioral defect in removing `torch` from the
application runtime dependency set. No production or script code imports
`torch`, the previous direct dependency pulled CUDA PyTorch wheels through a
dedicated index, and the existing supply-chain audit had already identified
that default runtime shape as over-broad without an owning feature.

Focused verification confirmed no Python import of `torch`, the PyTorch CUDA
index/source metadata is removed from `pyproject.toml`, and
`uv run --no-sync deptry .` no longer reports `torch`. The lockfile can still
contain PyPI `torch` transitively through dev tooling, but the application no
longer declares it directly. Deptry still reports planned residual findings for
`playwright_stealth` and `prompt_toolkit`, which remain open under
W04.P12.S41-S42.

## W04-004 | INFO | Playwright stealth dependency placement review found no defects

Status: verified with scoped residual.

The W04.P12.S41 review found no behavioral defect in moving
`playwright-stealth` from the dev group to runtime dependencies. Production
browser code imports `playwright_stealth` from `PlaywrightStealthEvasion`, and
`BrowserSession` defaults to that strategy, so the dependency belongs beside
runtime `playwright`.

Focused verification passed the existing browser evasion test, both live and
clean-export lock checks, and Deptry no longer reports `playwright_stealth`.
Deptry remains red for planned residual dependency findings and unrelated scan
noise, including an unrelated syntax warning in
`src/aeat/application/modelo/__init__.py`; those are outside S41.

## W04-005 | INFO | Prompt toolkit runtime declaration review found no defects

Status: verified with scoped residual.

The W04.P12.S42 review found no behavioral defect in adding a direct
`prompt-toolkit` runtime dependency. Wizard production code imports
`prompt_toolkit` directly for console validation and typed input/output
construction, so relying only on `questionary`'s transitive dependency left the
runtime declaration under-specified.

Focused verification passed the wizard dependency/import and prompt round-trip
tests, both live and clean-export lock checks, and Deptry no longer reports
`prompt_toolkit`. The W04.P12 original dependency findings are closed; Deptry
still reports broader transitive scan noise outside this phase.

## W04-006 | INFO | Google API executable protocol dead-code review found no defects

Status: verified with scoped residual.

The W04.P13.S43 review found no behavioral defect in replacing the
`_ExecutableRequest.execute()` protocol's named optional parameters with a
variadic structural signature. The Google adapter remains coupled only to the
presence of an `execute()` callable, and `execute_request()` still passes the
Google client's supported `num_retries` keyword at runtime.

Focused verification confirmed Vulture no longer reports the Google API
protocol parameter names, the Google API request tests still pass including the
retry propagation assertion, and Ruff passes for the touched adapter/test
surface. Remaining Vulture findings are the planned W04.P13.S44-S46 residuals.

## W04-007 | INFO | Secure-object CursorResult dead-code review found no defects

Status: verified with scoped residual.

The W04.P13.S44 review found no behavioral defect in removing the unused
`CursorResult` runtime import from the secure-object SQL repository. The two
rowcount use sites now cast to a local structural `_RowcountResult` protocol,
preserving the rowcount contract without importing SQLAlchemy's concrete DML
result type.

Focused verification confirmed Vulture no longer reports the secure-object
`CursorResult` import, the secure-object SQL test module passes, and Ruff passes
for the exact S44 commit-candidate repository blob. Live worktree Ruff remains
blocked by a pre-existing line-length issue in the same file's unrelated
docstring edit. Remaining Vulture findings are the planned W04.P13.S45-S46
residuals.

## W04-008 | INFO | Submission draft-loader protocol dead-code review found no defects

Status: verified with scoped residual.

The W04.P13.S45 review found no behavioral defect in making
`ModeloDraftLoader.load()` use a positional-only, underscore-prefixed draft path
parameter. The protocol still requires one `Path` argument and returns
`ModeloDraftLike`, while no discovered call site relies on a `draft_path=`
keyword contract.

Focused verification confirmed Vulture no longer reports the submission
protocol parameter, the submission protocol file passes Ruff, and the domain
submission tests pass. A broader adapter repository compatibility run exposed an
unrelated `ClassificationError` empty-message assertion failure outside the
protocol change. Remaining Vulture findings are the planned W04.P13.S46 CLI
documentation payload imports.

## W04-009 | INFO | CLI doc-reference payload import review found no defects

Status: verified.

The W04.P13.S46 review found no behavioral defect in binding the CLI payload
schema modules into an explicit `payload_schema_modules` tuple after import.
The generator still imports the modules for their `@register_schema` side
effects before inspecting `SCHEMA_REGISTRY`; the tuple only makes that
registration surface observable to dead-code analysis and guards against a
failed module import.

Focused verification confirmed Vulture reports no remaining production
dead-code candidates, Ruff passes for the CLI doc-reference surface, and the
CLI doc-reference conformance gate passes under the `docs` marker. Broader
language-pinning and write-if-changed edits already present in the worktree are
left uncommitted by this S46 slice.

## W04-010 | INFO | CSV/XLSX tabular provider consolidation review found no defects

Status: verified with scoped residual.

The W04.P14.S47 review found no behavioral defect in moving shared bank-layout
row projection into the CSV provider helper module and routing XLSX ingestion
through it. The consolidation stays inside the existing financial-provider
boundary: CSV still owns byte decoding and dialect detection, while XLSX still
owns workbook selection and typed cell mapping.

Focused verification passed Ruff for the touched providers, passed the CSV/XLSX
financial-provider and detection test suite, and ran `just audit-duplication`.
The duplication audit no longer lists a CSV/XLSX provider clone; remaining clone
groups belong to later W04.P14 rows or unrelated shifted-worktree changes.

## W04-011 | INFO | GROI/NIF-IVA oracle flow consolidation review found no defects

Status: verified with scoped residual.

The W04.P14.S48 review found no behavioral defect in extracting shared
verdict-oriented checker-oracle mechanics into `_checker_oracle_flow.py`. GROI
and AEAT NIF-IVA still own their distinct oracle ids, URL plans, surface labels,
guard policies, and error messages; only repeated replay-operation, replay
decode, normalization, observed lookup, and field-comparison flow moved behind a
domain-local helper.

Focused verification passed Ruff for the touched oracle modules, passed the
GROI/NIF-IVA oracle test suite, and reran `just audit-duplication`. The audit
no longer reports the larger domain oracle flow clones, but it still reports an
import-block clone between the two oracle modules and adapter live-driver clones
outside this domain slice. Adapter live-driver docstring edits already present
in the worktree were left outside the S48 commit.

Follow-up coverage added direct tests for `_checker_oracle_flow.py` with the
real `GroiObservation` model, so the helper contract is now covered directly as
well as through the sibling oracle suites.

## W04-009 | INFO | CLI doc-reference payload registration review found no defects

Status: verified clean.

The W04.P13.S46 review found no behavioral defect in binding the CLI
doc-reference payload imports into an explicit `payload_schema_modules` tuple
and asserting each import produced a loaded module name. The generator still
imports the same payload modules for their schema-registration side effects
before materialising the lazy CLI tree.

Focused verification confirmed the full configured Vulture scan is clean and
Ruff passes for the CLI doc-reference surface. The docs conformance tests pass;
the committed-reference drift test still fails because the live CLI includes
`app.live.filed.capture-all` while committed `docs/cli` has not been
regenerated. The worktree already contained unrelated doc-reference generation
edits, so the commit isolates only the payload-registration reference and Vault
tracking.

## W04-012 | INFO | Storage KDF salt codec consolidation review found no defects

Status: verified with scoped residual.

The W04.P14.S49 review found no behavioral defect in sharing the storage KDF
salt length and base64 codec helpers. The bucket manifest and master-key KDF
schemas still own their separate Pydantic models, validation entrypoints, and
exception semantics; the new helper only centralizes the repeated 16-byte salt
codec contract.

Focused verification passed Ruff for the touched storage surface and passed
the manifest/master-key KDF tests. `just audit-duplication` no longer reports
the manifest/KDF overlap; the remaining 21 clone groups are outside this S49
slice and remain scheduled for later review rows.

Follow-up coverage added direct tests for `_kdf_salt.py`, including exact byte
round-trip behavior and configured storage-error propagation.

## W04-013 | INFO | Locale traversal consolidation review found no defects

Status: verified with scoped residual.

The W04.P14.S50 review found no behavioral defect in moving repeated locale
traversal mechanics behind module-local helpers. `_ast_scanner.py` still
applies the same source-file skip rules, read/parse error logging, concrete-key
extractors, and namespace extractors. `manager.py` still edits YAML in-place
with the same newline preservation and leaf/namespace refusal semantics.

Focused verification passed Ruff for the locale surface and passed the locale
parity suite. `just audit-duplication` no longer reports the locale AST or
YAML traversal clone groups; 19 clone groups remain outside this S50 slice,
including a newly visible `_modelo_m036_cli.py` clone from shifted shared-tree
state.

## W05-001 | INFO | Semgrep scan-scope policy review found no defects

Status: verified with production residuals.

The W05.P15.S51 review found no defect in adding a root `.semgrepignore` that
excludes colocated test modules, test package trees, explicit test-support
fixture modules, and mirrored official data under `src/aeat/_data/` from the
existing production Semgrep lane. The policy does not suppress production
source paths and leaves the `just audit-security` command unchanged.

Focused verification confirmed Semgrep 1.165.0 is available and `just
audit-security` completes successfully. The scan skipped 17,238 files through
`.semgrepignore`, scanned 890 tracked files, and still reports 11 production
findings for later W05/W06 rows. The separate project-regression rule lane is
blocked before scanning by invalid YAML in `.semgrep/rules/no-any-annotation.yml`;
that pre-existing rule-file defect is outside this `.semgrepignore` policy
slice.

2026-06-05 follow-up: the project-regression rule loader defect is resolved.
`no-any-annotation.yml` now uses block scalar patterns for typed function
signatures, and custom rule paths are anchored for Semgrepignore v2 semantics.
The custom lane now runs 7 rules over 891 tracked files and reports 91 real
findings. The stock production lane still runs successfully with 11 findings.

## W05-002 | INFO | Mirrored data security disposition review found no defects

Status: verified with scoped residual.

The W05.P15.S52 review found no defect in adding a top-level
`src/aeat/_data/SECURITY.md` disposition for bundled data. The document keeps
the S51 Semgrep exclusion narrow: `_data` is outside the production source
security lane because mirrored official HTML/XML/PDF text and fixture literals
produce stock-rule noise, but the tree remains governed by provenance,
source-reference integrity metadata, no-private-data constraints, and untrusted
input parsing.

Focused verification passed the corpus provenance gate and reran the scoped
Semgrep production lane. The scan still reports 11 findings while scanning 891
tracked files and skipping 17,241 files through `.semgrepignore`. Existing
concurrent registry TOML edits under `src/aeat/_data` were not modified by this
documentation slice.

## W05-003 | INFO | Portal URL authority conformance review found no defects

Status: verified.

The W05.P15.S53 review found no defect in centralizing portal host and route
authority through external constants. Portal host enum values are now stable
registry keys, `_hosts.py` resolves those keys through configured AEAT domains,
portal entry paths come from `aeat.portal_paths`, and `PortalMetadata` validates
host and active filing/censo path shape against the same central registry.

Focused verification passed Ruff for the touched authority surfaces, passed the
portal suite, and passed the external-constants literal-centralization gate plus
overview calendar CLI tests. The gate caught residual bare Sede URL literals in
overview tests; those tests now use declared fixture helpers instead of raw
host strings.

## W05-004 | INFO | Remote-state planned-operation gate review found no defects

Status: verified with tracked residual.

The W05.P15.S54 review found no behavioral defect in the remote-state guard
changes. The new `assert_remote_operations_allowed` helper preserves the
existing fail-closed semantics while removing duplicated preflight loops from
the live-parity oracle path. The committed-registry gate uses real production
oracles and registry snapshots, not fakes, to prove that every currently bound
oracle plan is accepted by its declared read-only guard policy.

Focused verification passed for Ruff on touched registry surfaces, remote-state
guard tests, live-parity tests, and all three production oracle adapter test
files. The review also recorded a non-blocking registry edge: M100 Renta WEB
Open has a production oracle and guard policy but no committed `oracle_id`
binding yet, so the S54 gate is ready for M100 but only covers it after that
separate legal-data binding lands.

## W05-005 | INFO | Ruff scratch/probe scope review found no defects

Status: verified with scoped residual.

The W05.P16.S55 review found no defect in adding Ruff `extend-exclude` entries
for root one-off investigation scripts and the M200 classifier scratch script.
The exclusions match the diagnostic audit's scratch/probe paths and do not
exclude package source under `src/aeat`.

Focused verification confirmed `pyproject.toml` passes Ruff and the full Ruff
invocation no longer reports `scratch_probe`, `run_p04_s11_test`,
`test_attachment_fix`, `test_m714`, or `classify_m200` paths. The full Ruff
lane still exits nonzero for unrelated scheduled findings in package and test
code; those remain open under the later W05/W06 rows rather than being hidden
by this scope correction.

## W05-006 | INFO | Modelo CLI envelope-emitter decomposition review found no defects

Status: verified with shared-worktree residual.

The W05.P16.S56 review found no defect in the shifted modelo CLI command
decomposition. Extracted modelo command modules import `_emit_envelope` from
`._common` directly, matching the established extracted command-module pattern,
and receive root-only selector/rendering helpers through explicit registration
dependencies rather than importing the legacy `_modelo.py` root.

Focused verification passed Ruff for the modelo root, extracted modelo command
modules, and the new CLI guard tests. The modelo Typer app imports and registers
the expected root commands and command groups. Real CLI tests for export and
work-id hinting passed. The new architecture guard tests pass; the size-budget
guard currently reports only unrelated dirty live-IVA WIP in `_app_live.py`
(`2135` working-tree lines versus budget `2117`). That residual is not part of
S56 and remains visible for the W05.P17 full quality-audit baseline.

## W05-007 | INFO | Parsing package public-surface review found no defects

Status: verified with broader CLI residuals.

The W05.P16.S58 review found no defect in removing private compatibility
aliases from `aeat.core.parsing.__init__`. The package initializer now exposes
only the public parser names while the implementation modules retain their
private helpers for package-local tests and targeted internal consumers.

Focused verification passed Ruff for the touched parsing and M036 CLI files,
passed the parsing package tests, and passed the parsing enrollment inventory.
The inventory caught one adjacent direct `date.fromisoformat()` bypass in the
M036 CLI surface; that caller now uses the public `parse_iso8601_date` boundary.
Broader CLI verification still reports two unrelated residual failures:
`test_work_calculate_enters_bucket_source_mesh_calculation_boundary` is a stale
source-inspection assertion after modelo CLI decomposition, and
`test_app_ledger_create_manual_transaction_persists_in_active_bucket` now feeds
an update rejected by the taxable-base plus IVA invariant.

## W05-008 | INFO | HTTPX certificate fallback review found no defects

Status: verified.

The W05.P16.S59 review found no defect in the shifted HTTPX fallback location.
The planned browser path no longer exists; the active implementation lives under
`auth/_certificate_backends/_httpx_fallback.py` and is selected only through
`CertificateBackend.HTTPX_FALLBACK`. `preload()` refuses browser-context use
with `AuthConfigurationError`, and `verify()` returns a closed handshake failure
without writing decrypted PEM/key material to temporary files.

Focused verification passed Ruff for the fallback, certificate dispatcher, and
certificate tests. The certificate test suite passed, including backend
selection, HTTPX fallback preload refusal, settings registration, and handshake
failure behavior.

## W05-009 | INFO | Filing-status token relocation review found no defects

Status: verified with staged-hunk isolation.

The W05.P16.S57 review found no defect in relocating `FilingStatus` to the
lightweight operator-surface model layer. The LIVE command-family contract and
the live CLI now consume `FilingStatus.FILED` directly from the operator-surface
authority. The token-only `_filing_status_token.py` shim and the overview-owned
`_status.py` enum module are deleted, and overview no longer re-exports the enum.

Focused verification passed Ruff, operator-surface contract tests, curated root
and app help tests, live-filed help tests, and compileall for the touched
surfaces. Because the shared worktree still carries unrelated overview
calendar-event WIP and live-IVA watchdog WIP, the S57 commit stages only the
filing-status relocation hunks for `overview/__init__.py` and `_app_live.py`.

## W05-010 | INFO | Closeout review found no new W05 blocking defects

Status: verified with advisory-red residuals.

The W05.P17.S61 closeout review found no new HIGH or CRITICAL defects in the
closed W05 remediation slices. The review rechecked the W05 review log, the
full repo-health diagnostics audit, the current vault plan, and the filing
status relocation surface that had required staged-hunk isolation.

Focused verification confirmed the retired `_filing_status_token.py` and
overview `_status.py` files are absent, `FilingStatus` resolves from
`aeat.application.operator_surface`, the live CLI registers the `filed` group
through that enum, and the vault plan validates. Earlier HIGH/CRITICAL findings
in this audit are marked remediated and remain superseded by their documented
fixes.

Residuals remain deliberately visible rather than hidden: the S60 quality audit
baseline is advisory red for type, structure, production complexity, duplication
inventory, and Semgrep inventory; dependency and dead-code lanes are currently
green. The shared worktree also contains unrelated documentation-build diffs in
`justfile` and `pyproject.toml`; those do not change the S60 quality-audit
recipes or policy lanes reviewed here.

## W06-001 | INFO | Modelo CLI command-complexity extraction review found no defects

Status: verified with scoped residual.

The W06.P19.S74 review found no behavior defect in the `_modelo.py` command
complexity extraction. The command callbacks still own Typer option signatures
and envelope emission, while query selection, row projection, calculate input
parsing, calculate advisory output, and amend preflight parsing moved into
private helpers in the same module. No new public command surface or alternate
application path was introduced.

Focused verification passed Ruff, compileall, bindings-list behavior tests,
work-calculate behavior tests, and an amend help probe. Complexity measurements
showed `bindings_list` reduced from Radon C (20) to B (10), `work_calculate`
from C (19) to A (4), and no `_modelo.py` function above the Complexipy
threshold of 20.

Residual: `_modelo.py` still has 26 pre-existing Ty diagnostics in row-splat
and revision-object typing areas, and the module maintainability index remains
C (0.00). Those are not hidden by this review and remain candidates for later
typed cleanup/module decomposition.

## W06-002 | INFO | Registry formula complexity extraction review found no defects

Status: verified with scoped residual.

The W06.P19.S75 review found no behavior defect in the registry formula helper
extraction. `initial_values` now delegates unknown-input, computed-input,
previous-filing projection, and per-casilla value construction checks to private
helpers while preserving the same validation error classes, translated messages,
and context keys. The M210 `m210_resolve_rate` evaluator now validates its four
arguments into a typed private argument bundle and delegates baseline lookup,
convenio-row lookup, and convenio-rate parsing to private helpers without adding
a new operator path or changing sentinel handling.

Focused verification passed Ruff, Ty, Radon, Complexipy, and 53 registry/modelo
tests covering the formula runtime plus M130 and M210 surfaces. Complexity
measurements now place `initial_values` at Radon A (4) and Complexipy 0, and
`_evaluate_m210_resolve_rate` at Radon B (6) and Complexipy 6.

Residual: `calculate_registry_snapshot` remains Radon D (22) in
`_formula_runtime.py`, and the broader M200 registry probe still fails on missing
previous-filing binding materialization for casilla `01494`. Those residuals are
not hidden by the S75 extraction and should remain candidates for later registry
runtime and M200 binding hardening work.

## W06-003 | INFO | Ledger projection complexity extraction review found no defects

Status: verified with scoped residual.

The W06.P19.S76 review found no behavior defect in the ledger projection
extraction. `ledger_review` now delegates filter parsing, backend query
construction, detail/list payloads, and rendered lines to private helpers while
preserving the same backend `query_ledger_review_rows` authority and envelope
schema. `rule_apply` now delegates dry-run candidate selection, first matching
rule lookup, dry-run payload/line rendering, and live result payload/line
rendering to private helpers while preserving the same application service for
live mutation.

The slice also repaired local `_ledger.py` type-boundary diagnostics without
changing runtime behavior: typed output schema class arguments, typed ledger-link
evidence payloads, mapping access for stale filed revisions, and mutable evidence
payload dictionaries.

Focused verification passed Ruff, Ty, Radon, Complexipy, the ledger bulk
classification suite, the ledger list-filter suite, the CLI review round-trip,
and the backend ownership test. Complexity measurements now place `ledger_review`
at Radon A (1) and Complexipy 0, and `rule_apply` at Radon A (4) and Complexipy
2.

Residual: two review-prefix UX tests still fail during import setup with a
profile-bound storage route mismatch before the reviewed command is reached, and
the backend help-vocabulary test still fails because `ledger review --help` does
not contain the expected `classification` filter token. Those failures remain
visible for later CLI/storage hardening work.

## W06-004 | INFO | Complexity residual ratchet review found no hidden green claim

Status: verified advisory-red.

The W06.P19.S77 review found no evidence that the phase summary or diagnostics
claim all-green complexity status. The committed baseline records the production
and top-level test complexity lanes as failing, preserves the full over-threshold
ratchet list, and identifies the next likely complexity targets. This is an
explicit residual ratchet rather than a silent pass.

Verification reran `just audit-complexity-production` and
`just audit-complexity-tests`; both still exit 1. The production over-threshold
count is 24, and the top-level test over-threshold count is 8.

## W06-005 | INFO | Ruff scratch/probe scope verification found no defects

Status: verified with broader Ruff residual.

The W06.P20.S78 review found the scratch/probe Ruff scope already present in the
committed `pyproject.toml` baseline. Full-tree Ruff output no longer includes the
named root scratch/probe artifacts from HEALTH-008. The step correctly avoids
absorbing unrelated dirty `pyproject.toml` edits from the concurrent
test-topology refactor.

Residual: `uv run --no-sync ruff check . --statistics` still exits 1 with 475
findings across docs tooling, contributor scripts, relocated test packages, and
production import/line-length issues. Those are not scratch/probe scope failures
and remain visible for the later hygiene rows.

## W06-006 | INFO | Dependency declaration drift verification found no defects

Status: verified green.

The W06.P20.S79 review found no dependency declaration drift requiring a
`pyproject.toml` change. `just audit-deps` invokes deptry against `src/aeat`
with `aeat` declared as first-party and test paths excluded from the production
scan. The gate exits 0 after scanning 884 files and reports no dependency
issues.

Residual: none for dependency declaration drift in the current production
scope.

## W06-007 | INFO | Vulture dead-code verification found no defects

Status: verified green.

The W06.P20.S80 review found no dead-code candidate requiring source deletion or
suppression. `just audit-dead-code` runs Vulture with `pyproject.toml` and exits
0 with no current findings.

Residual: none for the configured Vulture lane.

## W06-008 | INFO | Semgrep security burn-down found no remaining findings

Status: verified green.

The W06.P20.S81 review found the prior Semgrep findings resolved without
weakening `.semgrepignore` into a production-source blanket exclusion. The
source-class policy still excludes mirrored legal data, tests, and explicit
test-support modules from the stock security lane, while production findings are
handled in source with exact allowlists or line-level rationale.

Material checks:

- ECB refresh now accepts only the canonical HTTPS ECB eurofxref endpoint before
  calling `urllib.request.urlopen`.
- Extraction-profile parser imports are constrained to the registry and inbound
  declaracion parser authority prefixes.
- CLI lazy imports are constrained to the registered command-module set.
- Controlled bootstrap SQL, POSIX private directory mode, Python `>=3.13`
  importlib.resources usage, and hard-coded cross-domain registration imports
  carry exact Semgrep rationale at the audited line.

Verification passed `just audit-security`, scoped Ruff, scoped Ty, and focused
FX/registry pytest.

Residual: none for the configured Semgrep production-security lane.

## W06-009 | INFO | Duplication lane recorded an explicit residual ratchet

Status: verified advisory-red.

The W06.P20.S82 review found no hidden green claim. The duplication lane still
reports 36 clone groups, but the plan row allows either reduction or ratchet
recording. Given the breadth of the clone families and the concurrent dirty
shared-worktree state, an evidence-only residual ratchet is safer than a
cross-domain refactor.

Verification passed by running `just audit-duplication`. Current baseline:
853 Python files analyzed, 36 clone groups, 650 duplicated lines, 6,487
duplicated tokens.

Residual: duplication remains advisory-red. Work should continue in cohesive
subsystem slices rather than as one broad cleanup.

## W06-010 | INFO | Hard gate attempt correctly refused a green claim

Status: blocked, not green.

The W06.P21.S83 review found the hard-gate attempt accurately preserves the
failure state. The row is not checked, and the evidence identifies two distinct
blocker classes: local environment breakage around the locked/incomplete
`torch` install, and the active relocated-test topology creating unresolved
relative imports plus stale import-linter sanctioned test paths.

Residual: hard gates must be rerun after topology and environment repair. The
campaign must not close S83 while `just tooling-doctor`, `just audit-structure`,
`just lint`, `just typecheck`, and `just test` remain red.
