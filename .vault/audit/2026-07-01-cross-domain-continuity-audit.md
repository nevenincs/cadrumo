---
tags:
  - '#audit'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-01'
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

## Recommendations

No open code changes recommended from these reviews. Keep W09.P41.S307 and W09.P41.S324 as separate implementation steps. Keep the full M131 módulos coefficient-table oracle as future work outside S297 and S398; S297 closes the grounded datos-base binding projection, and S398 closes only the advisory regulatory-floor predicate and evidence guard.
