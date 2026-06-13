---
tags:
  - '#audit'
  - '#eliminate-shims'
date: '2026-05-13'
modified: '2026-05-13'
related: []
---



# `eliminate-shims` audit: `chore/eliminate-shims state audit`

## Scope and method

This is a broad state-of-the-branch hygiene and architectural-debt audit
of `src/aeat/` at HEAD (`20e63da1`) on branch `chore/eliminate-shims`,
749 commits ahead of `main`. Three reviewer passes already covered the
schema-driven wizard slice; this audit deliberately steps back to the
whole tree.

Methods used:

- Static grep / ripgrep across `src/aeat/**/*.py` for the patterns
  enumerated in the task brief (shim residues, transient-meta phrases,
  ignored-parameter idioms, lazy `__getattr__`, mock surface).
- AST + runtime introspection of every `pydantic.BaseModel` subclass to
  classify `model_config` against the project canonical triple
  `strict=True / frozen=True / extra forbid`.
- Runtime `aeat --help` invocation to verify CLI root surface.
- Direct execution of `audit_cli_translations()`,
  `audit_wizard_translations()`, and the error registry test.
- `git status` + `git diff --stat` for the concurrent-agent surface
  inventory.
- Sampling of every flagged location to read enough context to
  adjudicate true / false positive.

Excluded from scope: the wizard slice itself (already reviewed three
times), the renta-pipeline dirty files semantic correctness (they
belong to a sibling executor), the `.vault/` doc churn, and the
registry TOML drift under `registry/aeat/`. This audit reports
who-owns-what on those surfaces but does not adjudicate their content.

## Shim / partial-implementation inventory

The branch is named "eliminate-shims" and it shows: no
`# TODO: phase 2` / `# deferred` / `# shim` / `# bridge` /
`# replaces` / `_v2` / `_legacy` / `_old` markers anywhere in
production code under `src/aeat/`.

Residual hits that need adjudication:

| Path:line | Residue type | Apparent purpose | Recommendation |
| --- | --- | --- | --- |
| `src/aeat/domain/calculations/registry/test_audit_oracle_surface_compatibility.py:66` | `raise NotImplementedError` | Test-internal protocol stub used to assert an oracle compatibility surface call is never reached. | Keep. Negative-path scaffold. |
| `src/aeat/domain/calculations/registry/test_live_parity.py:82` | `raise NotImplementedError("audit-helper tests never invoke verify_payload")` | Test-internal stub guarding that the audit-helper code path never reaches a payload verifier. | Keep. Enforces a negative pre-condition. |
| `src/aeat/application/filing/_review.py:448` (`_load_transaction_catalogue`) | `del path` ignored parameter | Function accepts `path` to satisfy a caller path-shape API but ignores it because the transaction catalogue is now SQL-backed via `SecureObjectRepository`. | Drop the parameter and update callers - the eliminate-shim move. |
| `src/aeat/application/filing/_review.py:467` (`_read_transaction_catalogue`) | `del path` ignored parameter | Same shape: `path` is ignored because transaction data is not file-backed. | Drop the parameter. |
| `src/aeat/domain/usage_ratios/_service.py:34` (`load_usage_ratios`) | `del path` ignored parameter | Public function still exposes a `path: Path` parameter the SQL-backed implementation discards. | Drop `path` from the signature. Textbook eliminate-shim. |
| `src/aeat/domain/usage_ratios/_service.py:84` (`save_usage_ratios`) | `del path` ignored parameter | Mirror of `load_usage_ratios`. | Drop `path` from the signature. |
| `src/aeat/adapters/persistence/storage/blob_store/_blob_store.py:329` | `del path` | The `_iter_manifests_with_paths` helper yields `(path, payload)` pairs but the public `iter_manifests` ignores the path. | Keep. Local pattern; rotation needs the path, iteration does not. |
| `src/aeat/entrypoints/cli/_config.py:354` | `del ctx` | Typer callback ignores the click context - standard Typer idiom. | Keep. Typer convention. |
| `src/aeat/adapters/outbound/aeat/browser/test_session.py:84,106,122,130` | `del kwargs` | Test-fixture spies that signature-match a wider-arity browser entry-point. | Keep. Test seam. |

No private-API duplicate / parallel-implementation pairs were found.
`_v2`, `_legacy`, `_old` suffix grep over `src/aeat/` returns only
test-internal `key_old` / `engine_old` / `repo_old` variable names in
master-key-rotation tests where the test variable is named "old"
because the test rotates from old to new - semantically correct.

The lazy `__getattr__` module hooks are inventoried separately below.

## CLI root surface

Runtime probe (`uv run --no-sync aeat --help`) confirms exactly two
top-level commands:

```
Commands
  config  Gestionar configuracion local y diagnosticos
  app     Espacio de trabajo fiscal para libros, facturas y declaraciones
```

`src/aeat/entrypoints/cli/__init__.py` registers the root tree at
module-import time with no env-var / feature-flag conditional. The
only conditional in the file is the `_app_import_error` branch: if the
`app` subtree modules cannot be imported (missing dependency), the
root replaces the live `app` Typer with an `_import_failure_surface`
that prints a guidance message and exits non-zero. The fallback still
registers under the `app` name; it does NOT register a third root.
No risk of a third top-level command under any code path.

## Pydantic strictness coverage

Methodology: imported every module under `aeat.*`, walked every
`BaseModel` subclass owning the class (`__module__` filter), and
inspected `model_config` for `strict=True`, `frozen=True`,
extra forbid.

`BaseSettings` subclasses (`aeat.core.config.Settings`) are excluded -
pydantic-settings models are mutable by design. The wizard helper
`_DummyAnswers` and similar test-only fakes are acceptable non-strict
locally.

Boundary-crossing records still missing strictness:

| Path:line | Class | Current model_config | Severity |
| --- | --- | --- | --- |
| `src/aeat/application/auth/_models.py:10` | `AuthState` | frozen=True, extra=forbid, **strict=False** | HIGH - persisted local-state record |
| `src/aeat/application/auth/_sessions.py:48` | `AuthenticatedAeatSessionResult` | frozen=True, extra=forbid, **strict=False** | HIGH - boundary record |
| `src/aeat/application/auth/_sessions.py:63` | `PersistedAuthSession` | frozen=True, **extra=ignore**, strict=False | HIGH - persisted record + extra=ignore actively permits unknown fields |
| `src/aeat/adapters/outbound/aeat/auth/_session_store.py:20` | `PersistedBrowserSession` | frozen=True, extra=forbid, **strict=False** | HIGH - persisted browser session |
| `src/aeat/application/profile/_models.py:12` | `ProfileRecord` | frozen=True, extra=forbid, **strict=False** | HIGH - persisted profile record |
| `src/aeat/application/workflow/_models.py:33,76,95` | `WorkflowEvent`, `DeclarationPointer`, `WorkflowState` | frozen=True, extra=forbid, **strict=False** | HIGH - persisted workflow state |
| `src/aeat/application/review/_models.py:136,165,183` | `LedgerSplit`, `LedgerReviewRecord`, `InvoiceReviewRecord` | frozen=True, extra=forbid, **strict=False** | HIGH - review-queue persisted records |
| `src/aeat/application/invoices/_importing.py:24` | `InvoiceImportResult` | frozen=True, **strict=False, extra=None** | MEDIUM |
| `src/aeat/application/invoices/_linking.py:21` | `InvoiceTransactionLinkResult` | frozen=True, extra=forbid, **strict=False** | MEDIUM |
| `src/aeat/application/invoices/_projection.py:16,32` | `InvoiceReviewProjection`, `InvoiceMatchProjection` | frozen=True, **strict=False, extra=None** | MEDIUM |
| `src/aeat/application/invoices/_queries.py:25` | `InvoiceListRow` | frozen=True, extra=forbid, **strict=False** | MEDIUM |
| `src/aeat/application/invoices/_reconciliation.py:21,31` | `ReconciliationSkippedSuggestion`, `InvoiceReconciliationResult` | frozen=True, extra=forbid, **strict=False** | MEDIUM |
| `src/aeat/adapters/outbound/aeat/sede/_declarations.py:126` | `Declaration` | strict=False | HIGH - outbound sede record |
| `src/aeat/adapters/outbound/aeat/sede/_notifications.py:67,116` | `RemoteNotification`, `NotificationsSnapshot` | strict=False | HIGH - outbound sede records |
| `src/aeat/adapters/outbound/aeat/sede/_schema.py:43-196` | `Expediente`, `JustificanteRef`, `SedeCapture`, `FiledDeclarationArtefact`, `ObservedCasillaValue`, `FiledDeclarationObservation` | strict=False (via `_STRICT_FROZEN` alias that omits strict) | HIGH - entire sede capture surface |
| `src/aeat/entrypoints/cli/registry.py:74,101,113,138,152,167,183,195` | `RegistryTreeReport` and 7 sibling JSON-output records | frozen=True, **strict=False, extra=None** | LOW |
| `src/aeat/domain/calculations/registry/_queries.py:26-129` | 10 `ModeloListRow` / `ModeloListReport` / etc. report rows | frozen=True, **strict=False, extra=None** | LOW |
| `src/aeat/domain/calculations/registry/_bindings.py:688,700` | `_OperatorClaveAccumulator`, `_OperatorClavePeriodAccumulator` | strict=True, extra=forbid, **frozen=False** | MEDIUM |
| `src/aeat/domain/calculations/registry/_bindings.py:850,1014,1129` | `_OssIossLedgerSelector`, `_IvaLedgerSelector`, `_RentaLedgerExpenseSelector` | frozen=True, extra=forbid, **strict=False** | MEDIUM |
| `src/aeat/domain/normatives/_schema.py:134,208` | `_NormativeStrictMutable`, `NormativeCatalogue` | strict=True, extra=forbid, **frozen=False** | MEDIUM |
| `src/aeat/domain/vat/_schema.py:177,332` | `_VatStrictMutable`, `VATCatalogue` | strict=True, extra=forbid, **frozen=False** | MEDIUM |
| `src/aeat/adapters/persistence/storage/master_key/_recovery.py:61,77` | `RecoveryKey`, `WrappedMasterKey` | strict=False | HIGH - wrap/unwrap secrets |
| `src/aeat/adapters/persistence/storage/secret_store/_secret_store.py:127` | `_SecretIndex` | strict=True, extra=forbid, **frozen=False** | MEDIUM - mutable index by design |
| `src/aeat/core/json_contract.py:62` | `OutputRootSchema` (generic) | strict=True, frozen=True, **extra=None** | LOW |
| `src/aeat/adapters/outbound/llm/_models.py:*` | 10 LLM record / cache / usage models | strict=True, frozen=True, **extra=None** | MEDIUM |
| `src/aeat/adapters/persistence/storage/sql/records.py:41,47,61,81` | `_StrictFrozen`, `ModeloRecord`, `PortalRecord`, `CorpusArtifactRecord` | strict=True, frozen=True, **extra=None** | LOW |
| `src/aeat/entrypoints/cli/data/ledgers/inventory.py:95,99,103` | `InventoryListJson`, `InventoryMutationJson`, `InventoryValuationJson` | strict=True, frozen=True, **extra=None** | LOW (runtime walk reports `InventoryValuationJson` twice - likely duplicate import-side effect) |

Total flagged: 83 BaseModel subclasses where at least one of
strict / frozen / extra=forbid is absent from the canonical triple.
The high-severity cluster is the application-layer persisted records
(`auth`, `workflow`, `review`, `profile`) and the outbound sede capture
records - these cross the persistence and AEAT-comms boundary and
should be the priority strictness sweep.

## Test hygiene

### Skips and xfails

| Path:line | Marker | Reason |
| --- | --- | --- |
| `src/aeat/adapters/persistence/storage/blob_store/_test_materialisation.py:109` | skipif(os.name != "posix") | POSIX-only file mode bits. |
| `src/aeat/adapters/persistence/storage/master_key/_test_master_key.py:414` | skipif(os.name != "posix") | Same shape. |
| `src/aeat/adapters/outbound/aeat/sede/test_renta_web_open_capture_replay.py:257` | xfail | Expected-to-fail until the AEAT sede capture surface stabilises. |

POSIX-only test variants are platform gates allowed by convention. The
single xfail warrants an executor look to confirm the failure mode it
describes is still real.

### Mocks

from unittest.mock, MagicMock, Mock( greps return zero hits across
src/aeat/. No-mocks mandate intact.

### Monkeypatch

monkeypatch.setattr appears 25 times across 4 files:

| Path:line | Target | Verdict |
| --- | --- | --- |
| `src/aeat/adapters/inbound/sanitizer/test_pipeline.py:188,199` | _fixtures.SANITIZED_SHAS (module-level frozenset constant) | Acceptable - patches a module-level fixture set. |
| `src/aeat/core/observability/test_replay.py:279,280` | fp_mod.PROJECT_ROOT, config_mod.PROJECT_ROOT | Acceptable - env-shaped constant redirect. |
| `src/aeat/adapters/persistence/storage/master_key/_test_master_key.py:251-615` (about 20 hits) | keyring.get_password, keyring.set_password, KeyringMasterKeyProvider._probe_backend, keyring.get_keyring | **VIOLATION** - patches a real KeyringMasterKeyProvider static method and the third-party keyring module class methods. Replace with a FakeKeyringBackend injection through the existing KeyringMasterKeyProvider constructor backend parameter. |
| `src/aeat/adapters/outbound/aeat/auth/test_authenticator.py:844` | authenticator_module.certificate_health | **VIOLATION** - patches a real component. Replace with an injection seam. |

### pytest.raises Exception too-broad catch

One hit:

| Path:line | Verdict |
| --- | --- |
| `src/aeat/adapters/persistence/storage/sql/_test_constraints.py:81` | **VIOLATION** - with pytest.raises(Exception) as excinfo. SQLAlchemy raises IntegrityError or a subclass; replace Exception with the specific class. |

### Deadweight assertions

assert True / assert 1 == 1: zero hits.

### Tautological-looking calculation tests

Sampled the patterns suggested by the rule. Findings:

| Path:line | Verdict |
| --- | --- |
| `src/aeat/domain/calculations/registry/test_modelo_180_round_trip.py:52-54` | **Borderline (allowed)** - copy-formula identity round-trip. Permitted per the rule Identity-round-trips carve-out. Prefer a graph-wiring assertion to avoid the Decimal-against-Decimal shape. |
| `src/aeat/domain/calculations/registry/test_modelo_190_193_round_trip.py:67-69` | Same shape as 180; same verdict. |
| `src/aeat/domain/calculations/registry/test_committed_registry.py:312-323` | OK - asserts values parsed out of a fixed-width AEAT export payload via parse_export_payload. Structural / round-trip parse test. |
| `src/aeat/domain/invoices/test_iva_classification.py:239-241` | **Borderline (review)** - the test author appears to apply VAT-rate times base in their head (1000 * 21% = 210). If the registry binding resolver does the same multiplication, this is a parallel-logic tautological pattern. Cross-check against workbook parity or VAT-rate parameter declaration. |
| `src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py:256` | Same shape: Decimal("310") for modelo-303-iva-soportado-interiores-cuota. Same review needed. |
| `src/aeat/domain/calculations/registry/test_ledger_renta_expense_binding.py:103-106` | **Borderline (review)** - observations are summed into casilla buckets. The test author sums the observation amounts (121 + 79 = 200) into the same bucket the resolver targets. The bucket-routing IS the test subject, but the Decimal-sum-against-Decimal-sum shape is the rule forbidden parallel-logic pattern. |
| `src/aeat/domain/calculations/registry/test_modelo_309_registry.py:122-123` | Identity-passthrough; allowed. |
| `src/aeat/domain/calculations/registry/test_modelo_349_registry.py:550-849` | Mixed - most are record-shape assertions (NIF strings, ejercicio). The numeric base/cuota assertions are inputs threaded through the resolver, so identity passthroughs. Allowed. |

Recommend a follow-up sweep specifically against the
_ledger_renta_expense_binding and _iva_classification tests: either
ground them against an AEAT workbook / oracle replay, or rewrite as
structural / graph-wiring assertions.

## Locale coverage

audit_cli_translations() returns () (zero failures).
audit_wizard_translations() returns () (zero failures).

A call-site grep finds two genuine orphan keys the audit functions
miss:

| Path:line | Key referenced | Why audit missed it |
| --- | --- | --- |
| `src/aeat/entrypoints/cli/filing/__init__.py:541` | cli.filing.import.<spanish-anno>_help (with non-ASCII tilde-n) | _CLI_KEY_PATTERN at src/aeat/application/wizard/_translations.py:81 is [A-Za-z0-9_]+ and rejects non-ASCII. The Spanish anno in the option name is invisible to the scanner. Tighten the pattern to a Unicode-word class or rename the key to ASCII-only. |
| `src/aeat/entrypoints/cli/registry.py:284` | cli.registry.metrics.<dynamic> | The call is an f-string concat (tr("cli.registry.metrics." + key)); the static scanner correctly skips it. The four locale files all have empty cli.registry.metrics: {} mappings, so any runtime call fails to resolve and renders the raw key string. Populate the metric subtree. |

The two orphans plus the audit-pattern blind-spot are HIGH severity:
they slip past CI today.

## Error registry consistency

Test run:

```
src/aeat/core/errors/test_registry_enforcement.py::test_every_aeat_error_subclass_has_a_registered_code PASSED
```

Zero orphans at HEAD. Prior reviewer concerns about ForalRegimeError,
IdentityError, and sanitizer entries are resolved.

## Lazy-compile workarounds

Four module-scoped __getattr__ hooks, all documented:

| Path:line | Purpose | Justification |
| --- | --- | --- |
| `src/aeat/domain/profile/__init__.py:36` | Defers PROFILE_KEYS materialisation so the wizard catalogue can import leaf modules without triggering the catalogue-driven build. | Breaks an import cycle between domain.profile._keys and application.wizard._catalogue. |
| `src/aeat/domain/profile/_keys.py:136` | Same intent at the leaf-module level. | Same as above. |
| `src/aeat/domain/portals/__init__.py:51` | Defers PORTAL_REGISTRY and helpers until first access. | Avoids materialising the portal registry at import time. |
| `src/aeat/domain/transactions/__init__.py:56` | Defers ImportSummary / TransactionCatalogueRepository import so the persistence layer does not pull in at package-import time. | Cited reason: SQLAlchemy + Alembic plugin setup logs to stderr and breaks JSON-CLI output. Real constraint. |
| `src/aeat/domain/normatives/__init__.py:67` (attribute level) | _LazyCatalogue.__getattr__ defers load_catalogue() until first attribute access on the singleton. | Acceptable lazy-cache pattern. |

Every hook has a load-bearing reason and is documented in its
neighbourhood. None of them is a code-smell hiding a misplaced
dependency at HEAD.

## Concurrent-agent surfaces

Dirty files in src/aeat/ (excluding .vault/, registry TOML, and
uv.lock) at audit start:

| File | Dominant feature | Owner stream |
| --- | --- | --- |
| `src/aeat/adapters/outbound/aeat/sede/test_renta_web_open_safety_live_proof.py` | Renta WEB Open safety guard | renta-pipeline |
| `src/aeat/application/review/test_edit_iva_rate_boundary.py` | IVA-rate edit boundary | review-stream |
| `src/aeat/domain/calculations/registry/_formula_runtime.py` | Bracket-lookup error-message line-wrap reformat | lint pass (no semantic change) |
| `src/aeat/domain/calculations/registry/_loader.py` | Trivial diff | restructure / lint stream |
| `src/aeat/domain/calculations/registry/test_cross_reference_applicability.py` | Test surface | calculations stream |
| `src/aeat/domain/calculations/registry/test_modelo_180_round_trip.py` | Round-trip test | calculations stream |
| `src/aeat/domain/calculations/registry/test_modelo_190_193_round_trip.py` | Round-trip test | calculations stream |
| `src/aeat/domain/calculations/registry/test_modelo_347_registry.py` | Modelo 347 registry test | calculations stream |
| `src/aeat/domain/calculations/registry/test_modelo_840_registry.py` | Modelo 840 registry test | calculations stream |
| `src/aeat/domain/renta/test_substrate.py` | RentaCCAA enumeration test (formatter only) | renta-pipeline |
| `src/aeat/domain/rental/_imputacion_parameters.py` | LIRPF art.85 parameters (formatter only) | rental stream |
| `src/aeat/domain/rental/_tier_resolver.py` | Tier reduction rate (formatter only) | rental stream |
| `src/aeat/domain/vat/_flow.py` | Flow direction sets (formatter only) | vat stream |

Untracked source file:

| File | Owner | Note |
| --- | --- | --- |
| `src/aeat/entrypoints/cli/test_error_boundary_integration.py` | error-registry stream | New integration boundary test that exercises command_error_boundary end-to-end through CliRunner. Independent of the wizard slice. |

Plus 109 untracked .vault/ documents (mostly the
2026-05-12-cli-workflow-redesign-* and 2026-05-13-cli-workflow-redesign-*
research/ADR fan-out from the restructure / CLI-redesign program).
These belong to the apex PM stream and are not in scope.

The diff-stat across src/aeat/ for dirty files is +42 / -64 lines,
weighted toward formatter / line-wrap normalisation. No semantic change
from concurrent agents is yet committed to the index.

## Forbidden-phrase grep

Strict reading of the no-transient-meta-in-source rule
(historically | previously | formerly | replaces | legacy | excised |
rebuild pending | UX-NNN):

| Path:line | Phrase | Verdict |
| --- | --- | --- |
| `src/aeat/entrypoints/cli/_declaration.py:196` | "The audit (UX-021) flagged Siguiente: resolve-blockers as an opaque recipe token..." | **VIOLATION** - dev-process metadata in a production docstring. |
| `src/aeat/entrypoints/cli/test_workflow_surface.py:1036` | "aeat --help must expose Typer completion install/show options (UX-013)." | **VIOLATION** - process metadata in test docstring. |
| `src/aeat/entrypoints/cli/test_workflow_surface.py:1038` | "The audit UX-013 listed shell completion as a separate feature request." | **VIOLATION**. |
| `src/aeat/entrypoints/cli/test_workflow_surface.py:1056` | "UX-021: the previous output reported only an aggregate count Bloqueos: 2..." | **VIOLATION** - both UX-021 and the previous output. |
| `src/aeat/application/overview/__init__.py:27` | "Closes UX-008 from the 2026-05-08 CLI gap audit recompile..." | **VIOLATION**. |
| `src/aeat/application/overview/__init__.py:194` | "UX-008 (calendar silently omits modelos when profile facts are...)" | **VIOLATION**. |
| `src/aeat/application/overview/test_calendar.py:279` | "UX-008 root cause: the deadline engine modelo-applicability..." | **VIOLATION**. |
| `src/aeat/application/topics/__init__.py:3` | "Closes UX-015 from the 2026-05-08 CLI gap audit..." | **VIOLATION**. |
| `src/aeat/domain/calculations/registry/test_text.py:14` | "the previous <[^>]+> stripper regex matched across lines..." | **VIOLATION** - describes a historical state of the code. |
| `src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py:57` | "The previous implementation converted the certificate and private key to plaintext temporary files" | **VIOLATION** - historical-state phrasing. |
| `src/aeat/adapters/inbound/justificante/_extract.py:124` | "Stricter than the previous [0-9A-Z]{8,12} pattern" | **VIOLATION** - restate without the temporal compare. |
| `src/aeat/domain/invoices/test_validators.py:76` | "ABEH CIF leaders historically accept either digit- or letter-control form." | **OK** - AEAT domain history, not codebase history. |
| `src/aeat/core/identity/_tax_id.py:41` | "either form (both historically in circulation)" | **OK** - domain history of tax-ID checksum forms. |
| `src/aeat/adapters/inbound/sanitizer/_dynamic.py:223` | "Bookmarks have historically retained the redacted term..." | **OK** - documents PDF bookmark behaviour. |
| `src/aeat/core/observability/_replay.py:28` | "# Legacy flags removed from the workflow CLI surface." | **VIOLATION** - describes a past state. Delete the comment. |
| Other legacy hits across sanitizer/vat/justificante/financial/filing/master_key/sede/classification/observability | Domain-noun usage (legacy DocInfo dictionary, legacy R14 rule, legacy 2021 modelos, legacy adapter enum names, legacy except-ValueError callers) | **OK** - domain nouns, not dev-process metadata. |

Total transient-meta source violations: 12 (counting each UX-### plus
the three "previous ... X" patterns plus the _replay.py:28 stale
comment). All are docstring / comment edits; no behaviour changes
required.

## __all__ surface hygiene

Walked every __init__.py under src/aeat/. One mismatch:

| Path:line | Issue |
| --- | --- |
| `src/aeat/adapters/outbound/llm/_providers/__init__.py:10` | __all__ includes private names _DeterministicAdapter and _ProviderAdapter. Either rename these symbols (drop the leading underscore) or remove them from __all__ and expose them through an explicit private-helpers module. |

Every other package __all__ either matches its public surface or is
intentionally omitted (sub-namespace packages that only re-export from
the parent).

## Severity-ranked findings

### HIGH

- **Persisted records missing strict mode.** 8+ application-layer
  records (AuthState, WorkflowState, LedgerReviewRecord, ProfileRecord,
  PersistedAuthSession, PersistedBrowserSession, the sede capture
  cluster) cross the persistence boundary with strict=False. Sweep to
  add strict=True and audit PersistedAuthSession extra=ignore - that
  one actively permits unknown fields.
- **PersistedAuthSession extra=ignore.** Document the reason or
  change to extra=forbid.
- **Two locale orphans bypass audit_cli_translations().** The
  non-ASCII cli.filing.import help-key and the empty
  cli.registry.metrics.* family across all four locales. Tighten
  _CLI_KEY_PATTERN to a Unicode-word class and either populate or
  rename the keys.
- **pytest.raises(Exception) in SQL constraints test.**
  _test_constraints.py:81 catches Exception; replace with
  IntegrityError or the precise SQLAlchemy class.
- **Patched real components via monkeypatch.** 20+ monkeypatch.setattr
  calls in master_key/_test_master_key.py patch the keyring module
  class methods and KeyringMasterKeyProvider._probe_backend. Plus one
  in auth/test_authenticator.py:844 patching
  authenticator_module.certificate_health. Replace with injection
  seams.

### MEDIUM

- **del path ignored-parameter API shims.** 4 production functions
  (load_usage_ratios, save_usage_ratios, _load_transaction_catalogue,
  _read_transaction_catalogue) take a path argument they immediately
  delete. Drop the parameter and update callers; this is the textbook
  eliminate-shim move the branch is named for.
- **Borderline tautological calculation tests.** The
  _ledger_renta_expense_binding, _iva_classification,
  _ledger_iva_aggregation_binding, and 180/190-193 round-trip tests
  use the Decimal-against-Decimal shape that the rule borderline
  carve-out permits. Convert to graph-wiring / workbook-parity /
  oracle-replay assertions where feasible.
- **Transient-meta phrases in 12 source / test docstrings.** The
  UX-013/015/021/008 family plus three "the previous ... X" docstring
  patterns plus the core/observability/_replay.py:28 stale comment.
  Pure docstring rewrites; no behaviour change required.
- **Mutable strict-mode catalogues.** _NormativeStrictMutable,
  NormativeCatalogue, _VatStrictMutable, VATCatalogue, _SecretIndex,
  and the two _OperatorClave*Accumulator records are strict=True but
  frozen=False. Document why mutation is required or move to a
  frozen-builder pattern.
- **xfail in renta-web-open replay test.**
  test_renta_web_open_capture_replay.py:257 carries an xfail; verify
  the failure mode is still real and not stale.

### LOW

- **__all__ private-name leak in LLM providers package.**
  _DeterministicAdapter and _ProviderAdapter in
  _providers/__init__.py:10. Trivial rename or __all__ prune.
- **JSON-output records under entrypoints/cli/registry.py and
  domain/calculations/registry/_queries.py are strict=False.**
  Internal-to-CLI report shapes; not load-bearing right now.
- **InventoryValuationJson registered twice** by the runtime walk in
  entrypoints/cli/data/ledgers/inventory.py:103. Likely import
  side-effect; verify there is only one canonical registration.
- **LLM models miss explicit extra=forbid.** All 10 _models.py classes
  are strict + frozen but extra=None. Add extra=forbid for
  completeness.

## Out-of-scope

- **Wizard slice correctness.** Three reviewer passes already covered
  the schema-driven wizard. This audit deliberately does not
  re-litigate that surface beyond confirming audit_cli_translations()
  and audit_wizard_translations() are clean and the wizard __getattr__
  cycle break is documented.
- **Concurrent-agent semantic correctness.** The 13 dirty src files
  and one untracked test file under other agents streams (renta,
  rental, vat, calculations, restructure / lint) were inventoried by
  ownership only. Substantive correctness belongs to those streams
  executors and reviewers.
- **.vault/ document churn.** 109 untracked .vault/ documents (mostly
  2026-05-12-cli-workflow-redesign-* and
  2026-05-13-cli-workflow-redesign-*) belong to the apex PM /
  restructure stream and are not adjudicated here.
- **Registry TOML and registry/aeat/ drift.** Dirty
  registry/aeat/modelos/100/manifest.toml is registry-content work,
  not src/aeat/ hygiene.
- **Pre-existing skips on POSIX-only test variants.** Standard
  platform gating, not a hygiene violation.
