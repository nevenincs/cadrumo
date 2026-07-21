---
tags:
  - '#audit'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-17'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` audit: rolling code review

## Scope

- Reviewed W09.P41.S323 changes to `src/aeat/domain/user_profile/_schema.py`, `src/aeat/_data/registry/aeat/user_profile/schema.toml`, and focused user-profile schema tests.
- Checked that the change remains schema-only for attribution-entity socios and does not implement the later `atribucion_member` resolver or M100 cross-profile linkage.
- Checked validation evidence from focused user-profile tests, touched-file ruff, vault plan check, and path-scoped diff check.
- Reviewed W09.P41.S410 changes to `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/deadline_windows/0003-modelo-202-2025-3p.toml`, `src/aeat/_data/registry/aeat/legal/tax-framework.toml`, `src/aeat/_data/corpus/aeat_official/calendars/files/calendario-contribuyente-2025.pdf`, and `src/aeat/domain/calculations/registry/tests/test_modelo_202_deadline_windows.py`.
- Checked that the 2025 `3P` direct-debit cutoff uses the year-specific AEAT 2025 contributor calendar, not only the general Modelo 202 instructions.
- Checked validation evidence from focused Modelo 202 tests, touched-file ruff, plan check, source-resolution, and corpus fingerprint verification.
- Reviewed W04.P19.S398 changes to `src/aeat/domain/calculations/registry/tests/test_modelo_131_regulatory_floor_predicate.py`.
- Checked that S398 closes on the shipped M131 `C01 -> C02` advisory predicate across all revisions, not on the rolled-back `C01 -> C07` predicate shape.
- Checked validation evidence from focused Modelo 131 registry tests, authority-backed application advisory tests, touched-file ruff, reviewer output, and RAG grounding.
- Reviewed W09.P41.S297 changes to `src/aeat/application/modelo/_calculation_actions.py` and `src/aeat/application/modelo/tests/test_modelo_131_data_base_binding_projection.py`.
- Checked that S297 projects only M131 datos-base fixed-record bindings into liquidation casillas `01` and `02`, preserves the official no-datos-base casilla `04` branch, and does not globally project arbitrary manual fixed-record bindings.
- Checked validation evidence from focused Modelo 131 registry/advisory/application tests, touched-file ruff, reviewer output, and RAG/reference grounding.
- Reviewed W09.P41.S292 current CLI provenance surfaces and `src/aeat/entrypoints/cli/tests/test_modelo_verification_report_view.py`.
- Checked that persisted `CalculationRevision.observations` are already exposed with `formula_id`, `legal_refs`, and `source_refs` through JSON revision payloads and the dedicated `work observations` sibling command.
- Checked validation evidence from focused CLI provenance integration tests, touched-file ruff, reviewer output, and RAG grounding.
- Reviewed W09.P45.S294 changes to `src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py`.
- Checked that the regression uses the real `ledger import` CLI path, a real CSV dry run, and the current canonical period grammar `--period 1T --year 2026`.
- Checked validation evidence from the focused ledger period grammar integration run, touched-file ruff, reviewer output, and RAG grounding.
- Reviewed W09.P45.S295 changes to `src/aeat/entrypoints/cli/tests/test_profile_import_idempotency.py` and the four locale files.
- Checked that the current D5 profile-import behavior remains identity-preserving, while operator text now distinguishes UUID collision from label collision and no longer describes `--label` as fresh-copy creation.
- Checked validation evidence from focused profile-import integration tests, touched-file ruff, locale scaffold/audit, reviewer output, and RAG grounding.
- Reviewed W09.P45.S239 changes to `src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py`.
- Checked that the broader historical ledger-import period testimonial is closed against the current canonical grammar: `--period 1T --year 2024` accepts, historical combined forms refuse, and bare `1T` without `--year` refuses on `ledger import`.
- Checked validation evidence from targeted ledger-import period tests, the full ledger period grammar file, touched-file ruff, reviewer output, and RAG grounding.
- Reviewed W09.P45.S312 changes to `src/aeat/application/aggregation/_iva_ledger.py`, `src/aeat/application/ledger/_preflight.py`, focused preflight tests, and locale catalogues.
- Checked that the W05.P24 D5 reject reasons are now live through ledger preflight and all supported locales, rather than remaining Hungarian-only scaffold extras.
- Checked validation evidence from focused ledger preflight tests, original intracom/export aggregation tests, locale scaffold/audit, placeholder parity, touched-file ruff, diff check, reviewer output, and RAG grounding.
- Reviewed W09.P45.S303 changes to `src/aeat/application/wizard/_commands.py`, `src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py`, and profile-validation locale leaves.
- Checked that profile-create wizard validation now catches pydantic `ValidationError` before the generic CLI boundary and renders concrete `--flag` details for the joint-taxation missing-spouse case.
- Checked validation evidence from the focused Rosa regression, the full profile lifecycle CLI module, touched-file ruff, locale scaffold/audit, direct isolated CLI output, reviewer output, and RAG grounding.
- Reviewed W09.P45.S283 as a no-code closure against the retired `src/aeat/diagnostics/profile.py` target.
- Checked that `aeat.diagnostics` was removed as an unapproved production package, the last pre-delete profile implementation already used `tr("cli.diagnostics.profile.errors.*")`, and current approved diagnostics/profile-adjacent modules do not contain the targeted `BadParameter` residual.
- Checked validation evidence from source/history searches, retired-surface tests, feature-scoped vault checks, reviewer output, and RAG grounding.
- Reviewed W09.P45.S284 changes to `src/aeat/application/wizard/_commands.py` and focused wizard/profile CLI tests.
- Checked that retired `aeat.diagnostics` secure-object code is not restored, locale CLI audit/scaffold output was already localized, and root `--version` remains the intentional machine-format semver path.
- Checked that wizard success text rows now localize `profile`, `status`, `active_profile`, and `next` labels while JSON payload keys and notice shape remain unchanged.
- Checked validation evidence from focused wizard tests, focused profile-create/edit CLI integration tests, touched-file ruff, reviewer output, and RAG grounding.
- Reviewed W09.P45.S236 changes to `src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py`.
- Checked that fresh `modelo work create` without `--revision` binds through the live registry authority for the supplied Modelo 131 year and period, while adjacent coverage preserves visible-target reuse and explicit revision mismatch refusal.
- Checked validation evidence from focused modelo work UX integration tests, touched-file ruff, reviewer output, and RAG grounding.
- Reviewed W09.P45.S237 as a no-code closure against current ledger classify/list/view/review/status behavior.
- Checked that current classify validation no longer falls through to the generic `config repair` boundary, status emits concrete `readiness_issue` rows, and the Taller Norte transcript shows same-profile status, list, review, classify, and follow-up ready status.
- Checked validation evidence from focused ledger classify/review/list/view integration tests, reviewer output, and RAG grounding.
- Reviewed W09.P45.S238 changes to `src/aeat/entrypoints/cli/_modelo_discovery_cli.py`, focused Modelo bindings CLI tests, the missing-filter fixture test, and locale catalogues.
- Checked that unscoped `modelo bindings list` output remains available for discovery but now warns through the shared typed `notices` channel and text output before operators copy binding ids into `work calculate`.
- Checked validation evidence from focused bindings CLI tests, schema conformance tests, placeholder parity, locale scaffold/audit, touched-file ruff, reviewer output, and RAG grounding.
- Reviewed W09.P45.S293 as a no-production closure against current missing-required verification finding language behavior and `src/aeat/application/modelo/tests/test_verification_finding_language.py`.
- Checked that current `_missing_required_casilla_finding` already renders through `tr()` and that the new regression switches a real active-profile language from Catalan to Spanish against a real Modelo 130 registry casilla definition.
- Checked validation evidence from the new focused application test, existing missing-required localization/provenance tests, touched-file ruff, reviewer output, and RAG grounding.
- Reviewed W09.P45.S231 as a no-production closure against current `--retencion-observation` schema validation behavior and focused CLI boundary tests.
- Checked that `_parse_typed_cli_observations` already catches pydantic validation and raises `typer.BadParameter` with flag and field detail before the generic command boundary can suggest `aeat config repair`.
- Checked validation evidence from focused Modelo typed-observation and error-boundary integration tests, touched-file ruff, reviewer output, and RAG grounding.
- Reviewed W09.P45.S229 changes to `src/aeat/entrypoints/cli/_overview.py` and `src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`.
- Checked that `overview calendar` now registers `--output-language` and `--language` using the real `OutputLanguage` authority and activates the override before date parsing, active-profile lookup, and all-profiles dispatch.
- Checked validation evidence from focused overview calendar CLI integration tests, touched-file ruff, reviewer output, and RAG grounding.
- Reviewed W09.P45.S224 changes to `src/aeat/adapters/inbound/financial/providers/_csv.py`, provider CSV tests, and focused ledger import UX tests.
- Checked that missing and blank CSV currency still default to the configured default currency, while malformed nonblank currency is refused at import with row and column context before `RawTransaction` or `LedgerTransactionPayload` validation can leak.
- Checked validation evidence from focused CSV provider tests, focused ledger import UX integration tests, touched-file ruff, reviewer output, and RAG grounding.
- Reviewed W09.P45.S222 changes to financial-provider date parsing, CSV row error wrapping, localized financial error leaves, and focused ledger import UX tests.
- Checked that malformed CSV dates now render the inner date-format reason through `errors.financial.unsupported_date_format` while retaining row, column, raw value, and expected-format context.
- Checked validation evidence from focused CSV provider and ledger import UX tests, locale scaffold/audit, touched-file ruff, reviewer output, and RAG grounding.
- Reviewed W09.P41.S320 retroactive locale-scaffold compliance for `iva_category_help` and `counterparty_eu_member_state_help` in the four locale catalogues.
- Checked that the target help leaves are structurally present in `en.yml`, `es.yml`, `ca.yml`, and `hu.yml`, and that the authoritative locale scaffold/check/audit commands pass after scaffold canonicalization.
- Checked validation evidence from RAG grounding, direct locale key search, `aeat.locales scaffold`, `aeat.locales scaffold --check`, and `aeat.locales audit`.
- Reviewed W09.P45.S234 changes to wizard IVA-regime visibility, profile validation/readiness, taxpayer projection, CLI choice derivation, and focused profile tests.
- Checked that natural-person profiles without `actividad_economica` do not store or require an invented `iva.regime`, while explicit IVA declarations, legal entities, attribution entities, and economic-activity natural persons preserve the existing regime behavior.
- Checked validation evidence from focused CLI integration tests, full taxpayer-type CLI integration tests, profile projection/completeness tests, wizard setup/status tests, Modelo applicability tests, setup/taxpayer-model focused tests, IVA choice/exempt tests, touched-file ruff, reviewer output, and RAG grounding.

## Findings

### w09-p41-s323 | low | no findings

No findings for the attribution-entity socios schema slice.

### w09-p41-s410-source-provenance | low | resolved calendar source provenance gap

Initial review found that the corrected Modelo 202 2025 `3P` direct-debit cutoff cited only `aeat-modelo-202-instructions`, while the `2025-12-17` cutoff is grounded in the year-specific AEAT 2025 contributor calendar. The finding was resolved by adding the `aeat-calendario-contribuyente-2025` source catalogue entry, bundling the official PDF corpus, and adding that source ref to the `modelo-202-2025-3p` deadline window. The bundled corpus was verified at `2206696` bytes with SHA-256 `dfdcae8889ab5fecffa368e235d933676c8a479915e09b107734f8339eed0f50`.

### w04-p19-s398 | low | no findings

No findings for the M131 regulatory-floor predicate regression. The current registry predicate is advisory-only, cites `rd-439-2007:art-110`, uses `implies_nonzero(["01", "02"])`, and keeps the rolled-back `implies_nonzero(["01", "07"])` shape absent. The new test does not overclaim predicate-local `source_refs`; it proves source grounding through revision and verification expectation source refs plus bundled corpus evidence.

### w09-p41-s297 | low | no findings

No findings for the M131 datos-base binding projection bridge. The change is scoped to Modelo 131, keeps explicit casilla inputs authoritative over projected backend values, leaves unrelated fixed-record bindings inert, and preserves liquidation casilla `04` as the no-datos-base computation from casilla `03`.

### w09-p41-s292 | low | no findings

No production-code findings for the CLI provenance surface. The row's sibling-command remedy is already present: `work observations` emits typed observation rows with `formula_id`, `legal_refs`, `source_refs`, and operand trace fields, while `work revision` and related JSON payloads carry the same typed observation envelope. One test fixture used a legal-ref-shaped value as a `source_ref`; it was corrected to a valid source id so the existing verification-report provenance test exercises the current schema contract.

### w09-p45-s294 | low | no findings

No findings for the ledger import period-regression guard. Production already refused the `2026T1` testimonial shape through the shared strict period parser; the new test pins the import verb specifically and asserts the refusal teaches `1T` plus `--year` rather than the retired `2026-Q1` shape. A reviewer rerun encountered unrelated dirty-tree collection failure from `PayerFact.REPORTING_PLATFORM_OPERATOR` drift in registry applicability labels; the S294-focused file had already passed `43` integration tests before that peer WIP surfaced.

### w09-p45-s295 | low | resolved test-prose drift

Initial review found no behavioral issue but identified stale test prose describing UUID-collision refusal as "already registered" while the new executable assertions require UUID/conflict wording and reject label-collision wording. The prose was corrected before closure. A final orchestration pass also removed stale fresh-copy wording from the `--label` help text. No findings remain for the locale wording or public-output tests.

### w09-p45-s239 | low | no findings

No findings for the ledger import period-regression closure. Production already uses the shared strict period parser for `ledger import`; the new real CLI tests pin the accepted canonical `1T` plus `--year` form and the intentional refusal of `2024-1T`, `2024/1T`, `2024Q1`, and bare `1T` without `--year`.

### w09-p45-s312 | low | no findings

No findings for the D5 IVA classification locale/readiness closure. The first Hungarian-only attempt failed correctly because those keys had no live code reference; the accepted implementation promotes the existing IVA counterparty/category validator for ledger transactions, maps its D5 reasons into ledger preflight, and adds matching English, Spanish, Catalan, and Hungarian detail leaves. The preflight tests prove both blocking readiness and Hungarian rendering.

### w09-p45-s303 | low | no findings

No findings for the profile-create validation specificity fix. The dynamic wizard command now formats leaked `SetupAnswers` pydantic validation entries with operator-facing flag names and raises a localized `BadParameter`, so Rosa's joint-taxation path names `--spouse-tax-id` and `--taxation-type` instead of falling through to the generic command-input validation boundary. The test covers the concrete testimonial path; other wizard validation shapes now share the same generic formatter.

### w09-p45-s283 | low | no findings

No findings for the no-code diagnostics-profile closure. The targeted file and package are absent by design after the unapproved `aeat.diagnostics` package removal, and the last pre-delete implementation already localized the listed refusal helpers. Current approved adjacent modules do not carry the targeted `BadParameter` sites, and no source/project references reintroduce `aeat.diagnostics` or stale `cli.diagnostics.profile.*` locale leaves. Reviewer Erdos noted only RAG index freshness lag, not a closure blocker.

### w09-p45-s284 | low | no findings

No findings for the mixed hardcoded-string follow-up. The accepted patch is scoped to the live wizard success text surface: text labels are now drawn from `application.wizard.output_labels.*`, while JSON keys remain stable and next-step guidance still rides the `notices` channel. The stale row fragments were handled by verification rather than code churn: retired `aeat.diagnostics` targets remain absent, locale CLI labels were already localized, and bare `aeat --version` remains a documented machine-format exception.

### w09-p45-s236 | low | no findings

No findings for the work-create registry-revision default regression. The live implementation already routes creation through `resolve_registry_revision_for_work_target`; the added CLI test pins the fresh-create no-`--revision` path against Modelo 131 and the registry authority's selected revision for the supplied year/period. The test uses the live registry authority as the expected-value source, so it proves CLI binding to the central resolver rather than acting as an independent legal oracle.

### w09-p45-s235 | medium | resolved review findings

The first S235 patch expanded the no-console `profile create NAME` recovery text but still advertised an unusable one-shot command because the natural-person filing baseline also requires `--name` and `--surnames`. The accepted patch adds those identity flags to the resident IRPF natural-person command in all locale catalogues and strengthens the real CLI regression to execute the advertised flag set with concrete values. The separate `profile create NAME --quiet` missing-flags refusal remains distinct, and the final code-review pass found no blocking issues.

### w09-p45-s234 | medium | resolved review findings

The first S234 review found that storage/readiness no longer invented `iva.regime`, but runtime taxpayer projection still defaulted a pure-landlord profile with no IVA fact to `GENERAL`. The accepted patch resolves that by projecting natural-person non-activity profiles as `IVARegime.NO_APLICA`, keeping explicit `EXENTO` and other operator-provided IVA regimes intact, and deriving CLI `--iva-regime` choices from the real wizard question so the internal sentinel is not exposed. No remaining S234 blocker was found after focused validation and local review.

### w09-p45-s237 | low | no findings

No findings for the ledger silent-profile-gate row. The current code no longer shows a profile-completeness gate on ledger `list`, `view`, `status`, or `classify`; classify validation is caught at the ledger boundary and status emits a concrete readiness issue instead of a silent block. The Taller Norte transcript now shows the original journey succeeding on one profile: status names the unclassified-row issue, list and review read the row, classify succeeds, and status becomes ready. Residual risk is limited to lack of one single S237-named all-verb fixture; the focused tests and transcript cover the reported behavior.

### w09-p45-s238 | low | no findings

No findings for the Modelo bindings unscoped-list warning. The implementation preserves broad discovery but emits `modelo.bindings.list.unscoped_revision` through the shared `Notice` envelope and mirrors it into text output when `--year` or `--period` is missing. The regression tests cover both missing filters, only `--period` missing, and the fully scoped no-warning path. Residual risk is limited to non-English translation wording quality; locale scaffold, audit, and placeholder parity passed.

### w09-p45-s293 | low | no findings

No findings for the missing-required-casilla Catalan drift closure. Production already uses `tr("application.modelo.findings.missing_required_casilla")` in the live verification-finding helper, and the new regression proves active-profile Catalan renders `La casella obligatòria` while Spanish renders `La casilla requerida` for the same real Modelo 130 casilla. Residual risk is limited to substring-level language assertions; existing tests cover key fallback, casilla interpolation, and registry provenance.

### w09-p45-s231 | low | no findings

No findings for the `--retencion-observation` input-validation closure. Production already uses the typed observation parser to convert malformed JSON object schemas into a `BadParameter` argument refusal; the new real CLI regression pins the missing-`scheme` testimonial path and asserts the flag name, field detail, and absence of `config repair` or stored-schema drift wording. Residual risk is limited to Typer's stable `Invalid value` prefix and existing mixed line endings in `test_errors_boundary.py`; `git diff --check` passed.

### w09-p45-s229 | low | no findings

No findings for the overview calendar output-language parity fix. The CLI verb now takes `--output-language` and `--language`, activates the override before any refusal path renders, and leaves application overview calendar internals untouched. Residual risk is limited to the alias not having a separate dedicated assertion; the help assertion and code review confirmed the alias is registered from the same Typer option declaration.

### w09-p45-s224 | low | no findings

No findings for the CSV currency/list-view validation closure. The fix keeps defaulting for absent or blank currency cells, rejects malformed nonblank currency at the CSV provider boundary with row and column context, and leaves strict ledger read-payload currency validation intact. Residual risk is limited to mixed-language provider detail inside the localized import wrapper, which matches existing provider diagnostic practice but remains a possible future localization-hardening domain.

### w09-p45-s222 | low | no findings

No findings for the CSV date-parse localization fix. Unsupported financial-source dates now carry a translated message key with label, raw value, and expected-format context; the CSV wrapper resolves that message before adding row context, so non-English ledger import refusals no longer leak the raw English `unsupported date format` string. Residual risk is limited to invalid compact-date behavior being manually verified by review rather than covered by a committed dedicated regression.

### w09-p41-s320 | low | no findings

No findings for the retroactive locale-scaffold compliance closure. The two requested ledger classify help leaves were already present in all four locale catalogues before the run, and the authoritative scaffold command preserved them while canonicalizing unrelated locale ordering and wrapping. `scaffold --check` and `audit` both passed for all four catalogues. Residual risk is limited to the expected scaffold churn being broader than the two target leaves.

### w03-p14-s223 | medium | resolved review findings

The initial S223 regression was helper-level and overstated its protection. The correction adds a real `build_draft` replay-path test with `renta-2024-profile-tax-residence-ccaa = "madrid"` in the flat input map, keeps the helper assertions as diagnostics, updates the Step Record wording, and removes unrelated generated feature-index drift. Residual risk is limited to not running a full CLI `work verify` journey.

### w09-p41-s392 | low | no findings

No findings for the historical M210 acceptance-test reconciliation. The current focused `test_modelo_210_convenio_rate_resolution.py` file contains Olivia GB/general, Khadija MA/interest, Felipe AR/pension domestic-tariff delegation, ZW non-Convenio missing-row handling, sentinel rewrite, representante predicate truth-table, and MA/interest anti-tautology mutation-pair gates. The focused M210 regression file passed before closure. No production or test code changed.

### w09-p41-s380 | low | no findings

No findings for the M210 full-engine ADR reconciliation. The accepted ADR already authorises the S380 scope, covers Phase 1 base computation, tipo-gravamen resolution, Convenio dispatch, and representante fiscal surfacing, and defers full design-record/treaty-roster wiring to the L3 Phase 2 engine plan. No ADR, code, registry, or test files changed.

### w09-p41-s393 | medium | resolved review findings

The accepted S393 patch keeps work-create applicability ordering intact while catching profile-projection validation only inside the applicability policy, allowing the existing readiness gate to surface missing non-EEA IRNR representative facts. The first approach was rejected because an early readiness call could have let pre-activity refusals beat not-applicable refusals. The final regression proves M210 engine-live legacy GB IRNR profiles missing `representante_fiscal_nif` and `representante_fiscal_nombre` get `REFUSED_MODELO_PROFILE_READINESS`, and a separate M130 overlap regression proves not-applicable still wins over pre-activity. Import-boundary review findings were resolved by using the package facades.

### w09-p41-s394 | low | no findings

No findings for the Convenio Espana-Marruecos follow-up reconciliation. The current cross-cutting treaty authority carries `MA` / `interest` as a `ceiling` row at `0.10`, grounded in `convenio-es-ma-1978:art-11` and `BOE-A-1985-9280`; the old Art 14 drift is absent from the scoped treaty and Modelo 210 surfaces. No stale `MA/general` row remains under Modelo 210, and the current resolver intentionally emits the missing-row blocking path when a treaty country has no matching income-type override. The focused M210 convenio-rate regression file passed before closure. No production or registry data changed.

### w09-p41-s395 | low | no findings

No findings for the Art 25.1.b pension follow-up reconciliation. The current Modelo 210 registry carries `m210-pension-tarifa-2025` as a grounded three-tranche bracket table under `trlirnr-rdleg-5-2004:art-25.1.b`, and the Spain-Argentina `AR` / `pension` treaty row delegates through `allocation_domestic_tariff` instead of a scalar fixed rate. The focused M210 convenio-rate regression file passed before closure. No production, registry data, or test code changed.

### w09-p41-s396 | low | no findings

No findings for the imputed-real-estate follow-up reconciliation. The current Modelo 210 registry carries `trlirnr-rdleg-5-2004:art-13.1.h`, the `aeat-irnr-renta-imputada-inmueble-urbano` source, imputation casillas and parameters, and the `m210_resolve_base_imponible` `tipo_renta="inmobiliaria"` branch. Focused M210 registry/application tests pass. No production, registry data, or test code changed.

## Recommendations

No open code changes recommended from these reviews. Keep W09.P41.S307 and W09.P41.S324 as separate implementation steps. Keep the full M131 módulos coefficient-table oracle as future work outside S297 and S398; S297 closes the grounded datos-base binding projection, and S398 closes only the advisory regulatory-floor predicate and evidence guard.
