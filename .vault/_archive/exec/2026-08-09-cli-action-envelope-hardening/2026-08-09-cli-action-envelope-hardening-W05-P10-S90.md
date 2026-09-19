---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:e5018976f998873ea248a7a437313e548a5e96267670101a5e1c35710fb5c565'
step_id: 'S90'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate ledger CLI action producers and co-located renderers without independently authored command prose, including direct typed-error consumer migration so canonical refusals reach the shared envelope intact.

## Scope

- Declared ledger CLI surface in `src/cadrumo/entrypoints/cli/_ledger*.py`.
- Co-located ledger CLI behavior, action-conformance, locale, and census evidence.
- `src/cadrumo/locales/{ca,en,es,hu}.yml` through the canonical locale authority.

## Description

- Remove CLI catches that flatten registered typed failures into `BadParameter` plus locally authored recovery commands.
- Remove or neutralize raw command/action prose in ledger help, refusal, notice, and operator-facing function help surfaces when no canonical catalogue action exists.
- Preserve `source_command` values solely as audit provenance, not operator guidance.
- Remove proven-orphan locale leaves and keep all surviving user-facing projections translation-complete.

## Outcome

`OutboundStorageError`, `CounterpartyEstablishmentConflictError`, `PurchaseInvoiceEvidenceInputError`, and `LLMClassifierError` now reach the shared typed boundary on their owned paths. No replacement action was invented where the canonical catalogue has no attach, withdraw, confirm, or manual-classification action identity.

The fixed-point sweep removed or neutralized direct action prose from link, doclink, counterparty confirmation, evidence extraction, pull-folder, rich-invoice link descriptions, split-child guidance, and LLM-rejection notices. Locale-authority mutations removed the orphaned `cli.ledger.classify.llm_failed`, `cli.ledger.doclink.refused`, and `cli.ledger.counterparty.errors.confirmation_conflict` leaves across ca/en/es/hu and reconciled the surviving link, pull-folder, and LLM notice leaves in all four locales.

Ruff, formatting, compileall, and diff checks pass. Real console checks for localized `ledger link --help` and `ledger pull-folder --help` pass and show no discarded command hint. S90 remains open for independent re-review.

## Notes

- The focused integration lane produced three passes; five failures and eleven setup errors are external to this delta: the shared profile helper lacks a newly required tax-residence flag and the local Ollama provider is unavailable.
- Focused census and recovery-rehoming lanes exceeded their execution windows and remain unverified. The census authority accepts an immutable Git revision, so the uncommitted working-tree delta cannot be reconciled honestly before coordinated ledger authorization.
- BasedPyright remains externally red on pre-existing CLI private-usage and unknown-type diagnostics; no diagnostic points to a changed line.
- The locale audit no longer reports an S90 orphan but remains externally red on unrelated missing schema/profile leaves.
- No compatibility bridge, manual disposition mutation, Git operation, or plan closure was added.

### S90 locale command-prose fixed point

The remaining eleven command-bearing `cli.ledger.*` catalogue leaves were rewritten through the canonical locale authority in Catalan, English, Spanish, and Hungarian. They now state neutral input, validation, and duplicate-review facts; executable command identity is no longer duplicated in localized help or refusal prose. A concurrent Hungarian catalogue writer was handled by the authority's guarded batch verb, without bypassing the write guard.

The conformance gate now resolves every `cli.ledger.*` leaf in ca/en/es/hu and rejects raw `aeat app ledger` or `app ledger` command tokens. Notice analysis follows module-bound names and local helper returns, so indirect raw strings and runtime translation defaults cannot evade the check. Runtime command literals in the covered modules are admitted only when their AST field is explicitly `source_command`; docstrings remain non-runtime documentation.

Verification: the strengthened integration module passes 5 tests; a separate fixed-point scan reports `COMMAND_VALUES ca 0`, `COMMAND_VALUES en 0`, `COMMAND_VALUES es 0`, and `COMMAND_VALUES hu 0`; real `add --help`, `attach --help`, and `classify --help` succeed in all four locales (12 direct console checks); Ruff and format checks pass. Locale scaffold remains globally red only on separately owned schema/profile omissions, one Modelo-work leaf, and the concurrent IVA-wallet cluster.

S90 remains open for final independent review.

## Final typed period-year refusal proof

The last reviewer-superset failure was a stale list-filter test that required the canonical `ledger-period-year-pairing` reason to be absent and instead matched reconstructed command guidance. The proof now invokes the real JSON CLI under ca/en/es/hu and asserts `REFUSED_REVIEW_FILTER_PARSE`, category `REFUSED`, condition `cli.ledger.filter.valid`, runtime-observation evidence with `ledger_filter_valid=false` and the canonical pairing reason, null action, `not_applicable` conditionality, and `operator_decision`. Both raw and safe input tokens are asserted redacted; no message or command prose is inspected.

Verification: the exact four-locale proof passes. The six-module reviewer selection collects exactly 73 tests and passes 73/73 in 197.58 seconds. The previously recorded import/conformance lane remains 35/35 and the application consent-withdrawal plus registry lane remains 25/25. Ruff, formatting, and Vault execution mapping remain clean for this scope, subject only to external historical Vault warnings.

S90 remains open for final independent review.

## Import UX test-integrity fixed point

The complete `test_ledger_import_ux.py` module was audited rather than retaining a notice-only subset. Every assertion coupled to rendered CSV-row, currency-column, invalid-date, validation, configuration-repair, expected-format, unsupported-format, or no-data prose was removed. Import behavior now binds the real JSON result DTO or the shared refusal envelope: error code and category, failed condition, exact evidence identity and provenance, typed runtime fact, null action, `not_applicable` conditionality, and `operator_decision` outcome. The invalid-date path proves the same machine contract under ca/en/es/hu without inspecting translated text. Provider choices are derived from `LedgerProviderID`, not redeclared as a test-owned accepted set.

A source-level conformance assertion now scans the whole import UX module and rejects direct rendered-output comparisons against string literals, case-folded presentation assertions, and a forced English invocation. JSON DTO member assertions remain admitted because they test canonical machine fields, not presentation. The exact source scan finds no `.lower()`, `.casefold()`, message regex, translated fragment assertion, or former rendered literals.

Verification selectors and results: `pytest -m integration -n 0 test_ledger_import_ux.py` passes all 23 cases; `pytest -m integration -n 0 test_ledger_import_ux.py test_ledger_notice_action_conformance.py` passes all 35 cases; `pytest -m "unit or integration" -n 0 test_consent_withdrawal.py test_registry_enforcement.py` passes all 25 cases. The requested reviewer superset collected 73 cases across exception propagation, evidence consent, import UX, list filters, ratios, and notice/action conformance; 72 passed and one separately located list-filter test failed because it asserts that canonical reason `ledger-period-year-pairing` is absent even though the live typed evidence now correctly carries that reason. This is outside the import UX file and is reported without weakening the canonical evidence or hiding the failure.

S90 remains open for final independent review.

## Canonical import notice transport closure

The final import payload review found three advisory strings redeclared inside `LedgerImportPayload`: dry-run preview, empty-import explanation, and likely-duplicate warning. Those fields duplicated the envelope's typed `Notice` authority and made machine consumers depend on localized prose embedded in a command-specific result schema.

The bespoke fields and their constructor parameters are removed. Import now emits the shared notice schema with stable codes `ledger.import.dry_run_preview`, `ledger.import.no_rows_imported`, `ledger.import.all_rows_skipped`, and `ledger.import.likely_duplicates`. Their contexts contain only deterministic import facts encoded as strings; every action is null because none of these observations identifies a genuine executable recovery. Text mode remains a localized projection of the same catalogue-owned message.

The integration proof asserts code, severity, context, and null action without matching rendered prose. The empty-import proof runs under Catalan, English, Spanish, and Hungarian and yields the same structural contract in every locale. Real import paths cover blank input, all rows skipped on re-import, dry-run would-import counts, and likely cross-format duplicates. A new AST conformance gate scans every ledger payload module and rejects future payload fields or constructor arguments ending in notice, hint, suggestion, or recovery.

Verification: the focused real-import selection passes seven tests; the complete import UX plus ledger notice/action conformance lane passes 33 tests. Ruff is clean. The exact ledger payload fixed-point scan returns zero bespoke advisory fields and only the canonical `LedgerImportPayload.from_result(result)` call remains. Direct-file BasedPyright reports only the package's known private-import and Typer callback diagnostics, with no diagnostic on the changed notice or payload declarations. `git diff --check` reports one pre-existing blank-line warning in the separately owned casilla-schema S29 execution record.

S90 remains open for final independent review.

### Frozen typed-error full-scope remediation

The frozen review identified remaining ledger CLI consumers that converted registered typed exceptions into `BadParameter` prose. Fresh semantic discovery re-confirmed the canonical split: `LLMConsentError` already owns a terminal LLM precondition verdict; transaction and invoice validation failures retain registered domain identities but require a fact-only CLI projection where no genuine operator action can be bound.

The evidence-extract consent catch was deleted, so `LLMConsentError` now reaches the shared boundary unchanged. Transaction-validation consumers in ledger add/update, M210 classification, lifecycle split, and all LLM classification paths now re-raise the same `TransactionValidationError` with condition `cli.ledger.transaction.valid`, typed error-kind evidence, no action, `not_applicable` conditionality, and `operator_decision`. Invoice add, wizard, import, update, and evidence-confirm consumers likewise preserve `InvoiceValidationError` under `cli.ledger.invoice.valid`. Pydantic validation in rich-invoice construction and classification-rule construction now reaches the shared validation boundary instead of exposing field/error prose. The adjacent evidence-consent re-derivation `ValueError` prose bridge was also removed.

The structural conformance gate now rejects typed ledger errors converted to `_bad` or text, and rejects caught exception text embedded in local `BadParameter` messages. Locale/source parity explicitly retains the registered `cli.ledger.errors.period_year_pairing` identity even though no presentation helper consumes it. Filter integration assertions now bind the exact machine reason and evidence facts rather than relying on absence of rendered prose.

A new real isolated CLI proof stores genuine structured evidence, invokes `ledger evidence extract --off-host-provider OPENAI --acknowledge-off-host` with deployment opt-in disabled, and observes `REFUSED_LLM_CONSENT`. It asserts failed condition `llm.evidence.off_host_dispatch_permitted`, exact application-state facts, `action=null`, `conditionality=not_applicable`, and `no_recovery_outcome=operator_decision`; `REFUSED_CLI_BOUNDARY` is explicitly rejected.

Verification: the isolated consent proof passes (1 passed in 5.39s). The full S90 ledger action conformance module plus the two focused filter-refusal cases pass (11 passed in 73.25s). Ruff is clean on the changed scope and `git diff --check` reports no owned whitespace errors. Direct-file BasedPyright remains unsuitable as a closure lane because the CLI package carries pre-existing private-import and Typer callback diagnostics outside the changed lines.

S90 remains open for independent review.

### Final import and consent re-derivation blockers

The remaining import bridge caught every `CadrumoError`, rendered it through `resolve_error_message`, accumulated `(path, reason)` strings, and finally emitted `_all_files_refused` as one `BadParameter`. That aggregation was removed. Per-file import now catches only `TransactionValidationError` long enough to attach the existing `cli.ledger.transaction.valid` fact-only verdict, then re-raises the same registered exception; every other registered error reaches the shared boundary unchanged. The two now-orphaned import refusal locale leaves were removed from ca/en/es/hu through the canonical locale authority.

Consent re-derivation now owns three distinct application predicates instead of raising raw `ValueError`: `ledger.consent_rederivation.artefact_available`, `ledger.consent_rederivation.transcription_available`, and `ledger.consent_rederivation.on_host`. The registered `ConsentRederivationError` carries the exact failed predicate, application-state evidence, no action, `not_applicable` conditionality, and `operator_decision`. The CLI performs no message matching or presentation reconstruction.

The conformance corpus already includes `_ledger_import_cli`; it now explicitly rejects `resolve_error_message`, `_all_files_refused`, and broad `CadrumoError` catch aggregation. A real isolated missing-CSV invocation proves `ERROR_TRANSACTION_VALIDATION` with condition `cli.ledger.transaction.valid`, typed error-kind evidence, and no generic `REFUSED_CLI_BOUNDARY`. Two real isolated consent re-derivation invocations prove the distinct missing-artefact and missing-transcription conditions and their fact-only terminal outcomes. The prior English sentence and regex assertions were replaced by structural condition/evidence/action/outcome assertions.

Verification: the complete selected integration lane passes 21 tests in 72.30s. Application consent-withdrawal plus registry enforcement passes 25 tests in 27.50s. Focused BasedPyright reports zero errors, warnings, or notes; Ruff and compile checks pass.

S90 remains open for final independent review.

### Locale-neutral exception-propagation proof

The final S90 test-integrity review found that `test_ledger_exception_propagation.py` forced English and distinguished the no-profile and corrupt-pointer branches by rendered phrases. The fixture-level language override and all message substring assertions were removed.

Both cases still drive the real `ledger ratios list` Click path against real sessionless storage. The cold-start branch now asserts the shared JSON spine's `profile.active.available` condition, canonical `operator.profile.create` reference, live `config.profile.create` command key, missing `profile_name` argument, and `requires_arguments` conditionality. The corrupt-pointer branch now asserts `REFUSED_CLI_VALIDATION_BOUNDARY`, the `cli.validation.boundary_clean` condition, exact runtime-observation evidence naming `CliValidationBoundaryError`, no action, `not_applicable`, and `operator_decision`. These assertions are locale-neutral and prove the exceptions remain categorically distinct without depending on translated prose.

Verification: the propagation module passes 2 tests. The combined reviewer integration selection covering propagation, consent, import, filter, ratios, and the ledger structural conformance gate passes 40 tests in 82.33s, exceeding the requested 39-case selection. Application consent-withdrawal plus registry enforcement passes 25 tests in 26.14s. Ruff check and Ruff formatting are clean after canonical formatting.

S90 remains open for final independent review.

## Coordinated rehoming reconciliation

After three identical read-only boundaries separated by at least sixty seconds, the canonical S50 migration wrote one 238-row postimage. The isolated target delta was exactly eight removals, four additions, and thirty-eight preserved target identities. The additions were exactly three `PurchaseInvoiceEvidenceInputError` fingerprints owned by S38 and one `LLMContentionError` fingerprint owned by S94; thirty-one separately recorded locator-only refreshes were incidental metadata.

The resulting ledger SHA-256 is `9de39139862dd9c4a057c981a3f9d47de401f37675616ed1745d3f254b0ce1e5`. Direct validation passed with `E_REHOMING_VALIDATED:238`, and all four target error families matched the live fingerprint multisets and declared owners exactly. The immediate no-write byte replay returned `E_REHOMING_MIGRATION_CHECK_CONTENT` after concurrent source movement; no second locator chase or write was performed. The complete 74-test lane finished with 71 passes and three externally concurrent failures: new Modelo error-family multiset drift in two tests and a source parse failure in `_action_resolution.py` in the owner-scope test.

This step remains open for independent review.
## Frozen Notice residual remediation

Fresh semantic discovery confirmed that neither the split-recommendation predicate nor the empty LLM-diagnostics predicate has a genuine action identity in the canonical operator-action catalogue. Both are observations, not executable recoveries: the split decision requires operator review, while absent metrics provide no safe transaction or classification inputs.

The two live Notice paths now render only their canonical localized fact keys, with no English default fallback, continuation sentence, synthetic `actionability` context, guessed action, or raw command. Their text mirrors the same Notice message rather than translating a second independently authored copy. The ca/en/es/hu catalogue values were narrowed through the locale authority to the same neutral facts.

Focused real JSON/Notice tests pass (2 passed), including explicit `action is None` and empty neutral context. Ruff and formatting pass. Exact residual search finds neither retired default continuation nor retired actionability identity. The immutable-HEAD census remains globally open on pre-existing campaign clusters and cannot observe this uncommitted delta. Locale audit remains externally red on unrelated schema/profile gaps and concurrent IVA-wallet leaves.

S90 remains open for independent review.

## Frozen independent-review closure

The independent review found indirect translation defaults whose values were first assigned to local names and then passed to `Notice.message`. The ledger Notice conformance gate now covers all thirteen Notice-bearing ledger modules and follows those local bindings, so direct and name-bound raw English defaults fail the same structural test.

All frozen name-bound defaults were removed from add/prorrata, idempotent no-op, bulk classify/import, invoice wizard/import, and counterparty fact notices. The two remaining `OutboundStorageError` catches in pull-folder were removed; list and per-document failures now reach the shared typed boundary without local `BadParameter` translation or `refusal_reason=str(exc)` flattening. The link-help proof now asserts a canonical invoice input description without a raw command hint.

Verification: the structural gate and real link-help CLI proof pass (3 passed); the bulk-classify real CLI notice proof passes; Ruff passes. Counterparty real CLI proofs remain blocked before the owned verb by the shared profile fixture omitting the newly required `--tax-residence-jurisdiction-scope`. Fixed-point census remains globally red on separately owned campaign clusters and immutable HEAD cannot observe this working-tree delta. BasedPyright remains globally red on pre-existing private-usage and Typer typing diagnostics.

The remaining presentation-localization debt is assigned to S41: 254 `tr(default=...)` calls under `_ledger*.py`, of which exactly 174 are help defaults and 80 are other presentation fallbacks. They are not action/continuation/recovery semantics and were deliberately not swept into S90.

S90 remains open for independent review.

## Absolute ledger locale closure

The operator's absolute locale rule supersedes the earlier S41 deferral recorded above. An AST inventory found 254 remaining `tr(default=...)` calls across sixteen `_ledger*.py` modules: 174 help fallbacks and 80 other presentation fallbacks, covering 226 distinct literal locale keys. Before mutation, every referenced key resolved to a nonempty authored value in ca/en/es/hu and all placeholder sets matched across the four catalogues.

A token-span, AST-enumerated mechanical rewrite removed exactly those 254 `default` keywords while preserving each key and every non-default interpolation argument. The S90 conformance gate now scans every `_ledger*.py` source module and refuses any future `tr(default=...)`, in addition to its thirteen-module Notice/action checks. The fixed-point result is zero runtime English or Spanish fallback prose in the declared ledger scope.

Verification: exact AST census reports `LEDGER_TR_DEFAULT_ZERO=True count=0`; Ruff, formatting, compileall, and diff checks pass; direct `aeat --language {ca,en,es,hu} app ledger --help` succeeds in all four locales. The help/conformance integration selection produced 31 passes and three unrelated failures at the pre-existing profile gate requiring `iva.m303_regime_composition`, before the changed operations ran. Locale scaffold remains globally red only on separately owned schema/profile omissions and IVA-wallet extras. BasedPyright remains globally red with 215 pre-existing private-usage, Typer typing, unused-callback, and unknown-type diagnostics; fallback removal introduced no typed construct.

S90 remains open for final independent review.
## Frozen invalid-date and locale-orphan remediation

The ledger LLM-diagnostics date parser no longer passes an independently authored English `default` through the shared parser. Its `BadParameter` message now resolves exclusively from `cli.ledger.llm_diagnostics.bad_date` with the option and rejected value as interpolation facts.

A source-wide literal-key inventory proved that `cli.ledger.pull_folder.errors.folder_refused` had no Python consumer and was the sole source-orphan `cli.ledger.*` leaf. The Spanish-only leaf was removed through the canonical `dev.locales remove` authority. The surviving `cli.ledger.*` key sets are identical across Catalan, English, Spanish, and Hungarian and every leaf has a source identity.

The S90 conformance corpus now includes every plan-declared module, adding `_ledger_rules_cli.py`, `_ledger_ratios_cli.py`, `_ledger_review_cli.py`, and `_ledger_support.py`. Name resolution walks function-local bindings as well as module bindings, and a separate structural assertion rejects helper-mediated `default=` arguments. These gates inspect syntax and locale ownership only; they do not reproduce ledger business logic.

Verification: the strengthened integration module passes seven tests; the focused helper/default and locale key-set gates pass two tests; the real `llm-diagnostics --since not-a-date` command passes four locale cases against the selected catalogue value. Ruff check and formatting pass. Locale scaffold remains globally red only on separately owned profile-schema, Modelo-work, and IVA-wallet catalogue drift; the S90-scoped parity/orphan gate is clean. Vault execution mapping is clean, with only pre-existing S38 markdown and S56 audit body warnings.

S90 remains open for independent review.

## Coordinated canonical rehoming reconciliation

A fresh read-only derivation established three identical stability boundaries separated by at least sixty seconds. Immediately before mutation, the canonical guard revalidated the ledger, plan, all-source, rendered postimage, structural-delta, and locator-delta hashes byte-for-byte. OWNER_ZERO was zero and every one of the twenty-four structural additions had exactly one open owner. The delta contained thirty-five removals, no historical-row, disposition, or current-identity changes, and 144 locator-only refreshes recorded as incidental metadata.

Exactly one S50 canonical-tool write produced the proven postimage. The resulting ledger SHA-256 is `bc6ddc3b5edddd852a155e48ca58ec6e3aa188f716cecef8615b9bef20de2aec`. Direct validation returned `E_REHOMING_VALIDATED:238`; the single immediate no-write replay returned `E_REHOMING_MIGRATION_CHECKED:238`. No second locator chase or write was performed. The complete canonical rehoming lane passed 74 tests.

This owner Step remains open for independent review and ledger reconciliation.
