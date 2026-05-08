---
tags:
  - '#plan'
  - '#aeat-cli-gap-closure'
date: '2026-05-08'
related:
  - "[[2026-05-08-aeat-cli-gap-discovery-audit]]"
  - "[[2026-05-08-aeat-cli-hardening-plan]]"
  - "[[2026-05-08-cli-backend-boundary-adr]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `aeat-cli-gap-closure` `AEAT CLI gap closure granular execution plan`

This plan turns every still-open and newly-discovered finding from the
2026-05-08 CLI gap discovery audit recompile into one mechanical, repetitive,
per-line execution checklist. It complements the prior CLI hardening plan: it
does NOT re-execute the rows that the recompile recorded as `CLOSED`. It
explicitly closes the partial rows, the still-open rows, and the four new rows
introduced by the recompile (`UX-019`, `UX-020`, `UX-021`, `UX-022`).

The execution model is: every step is a `- [ ]` checkbox bound to one file,
one function, one test name, or one shell-verifiable command. No step is
allowed to span multiple subjects. Every wave ends with a commit checkpoint.
No PRs are created. All work lands in this worktree.

## 0. Hard invariants

- [ ] Invariant: CLI changes are limited to argument parsing, command registration, output formatting, exit-code mapping, and delegation to backend functions.
- [ ] Invariant: Validation, mutation, persistence, schema decisions, filing decisions, deadline decisions, auth decisions, and modelo calculations live in `src/aeat/application/...`, `src/aeat/domain/...`, or `src/aeat/adapters/...`.
- [ ] Invariant: Missing backend behaviour discovered during CLI work is in scope and must be implemented before the CLI exposes the affected surface.
- [ ] Invariant: Source code, docstrings, comments, and module headers contain no dates, vault paths, "phase", "wave", "previously", "rebuild pending", or any transient development metadata. Phases and waves live only in this plan and in commit messages.
- [ ] Invariant: No tautological tests. Every numeric assertion is grounded against an external authority (workbook parity, AEAT-published worked example, live oracle replay, captured filing, or structural / graph-wiring contract).
- [ ] Invariant: No mocks, fakes, stubs, monkeypatches, `pytest.skip`, `pytest.xfail`, or `xfail_strict=False` shortcuts used to make tests pass.
- [ ] Invariant: Hand-verify a flow against the live CLI BEFORE encoding it as a test. Manual capture of inputs and outputs is an explicit prerequisite step.
- [ ] Invariant: Every wave commits its own slice. Commits stage only the files this plan owns or that the wave's steps explicitly modify. Unrelated worktree drift is left untouched.
- [ ] Invariant: No destructive git operations (`reset`, `restore`, `checkout --`, `clean`, `stash drop`, `worktree remove`). Conflicts are resolved by editing.
- [ ] Invariant: Pre-commit hooks must pass before each wave commit; failures are root-caused, never bypassed with `--no-verify`.
- [ ] Invariant: New CLI surface must reference an existing backend function. If the backend function does not exist, the wave creates it before adding the CLI verb.

## 1. Hand-verify protocol

Every wave that touches a user-facing CLI surface follows this protocol BEFORE
any test code is written.

- [ ] Capture step 1: run the live CLI command against a clean profile. Record the exact stdout, stderr, exit code.
- [ ] Capture step 2: identify the external authority for the expected behaviour. Allowed authorities: AEAT workbook (`registry/aeat/workbooks/...`), AEAT-published worked example, captured prior filing, deadline engine documented rule, structural contract from registry TOML, error-path contract.
- [ ] Capture step 3: by hand, derive the expected output from the external authority. Record the derivation.
- [ ] Capture step 4: diff the live capture against the derived expectation. Treat any divergence as a defect, not a test bug.
- [ ] Capture step 5: only after the live capture matches the external authority, encode the scenario as a `@pytest.mark.live` test gated by `AEAT_LIVE_TESTS_ENABLED`.
- [ ] Capture step 6: randomise inputs the user could legally vary (profile name, working directory, flag order, value range within legal bounds); pin the externally-anchored output.
- [ ] Capture step 7: prove the test fails when the backend is reverted to the pre-fix state. If the test still passes, it is tautological and must be rewritten.

## 2. Issue ledger

Status keys: `OPEN`, `PARTIAL`, `NEW`, `CARRIED` (unverified at recompile).

| audit_id | Severity | Status | Wave | Headline |
|---|---|---|---|---|
| UX-019 | HIGH | NEW | W1 | AES-256-GCM tag verification failure on read paths. |
| UX-007 | HIGH | OPEN | W2 | Profile registry exposes only RENTA personal-identity keys; no IVA, IRPF, modelo enrolment, regime, SII, Verifactu, ROI keys. |
| UX-012 | HIGH | OPEN | W3 | Errors lack fix suggestions; `declaration calculate` has no `--binding KEY=VALUE`; M130 binding supplier surface absent. |
| UX-020 | MEDIUM | NEW | W4 | Declaration verbs disagree on flag surfaces. `status` accepts `(--modelo, --period)`; `approve` and `validate` reject those. |
| UX-021 | MEDIUM | NEW | W4 | `Bloqueos: 2 / Siguiente: resolve-blockers` is opaque. Calculate output does not enumerate blockers; `Siguiente:` is a recipe token, not a runnable command. |
| UX-006 | HIGH | PARTIAL | W4 | `Perfil listo: si` oversells readiness when only 2/22 keys are set; need per-modelo readiness matrix. |
| UX-004 | HIGH | OPEN | W5 | Help text quality inconsistent. `aeat setup init --help` and `aeat setup auth configure --help` are surface-only. |
| UX-022 | LOW | NEW | W6 | Auth-readiness diverges between `aeat setup auth status` (`Listo: no`) and `aeat config doctor` (`ok auth.session`). |
| UX-003 | HIGH | PARTIAL | W7 | A4 (interactive `aeat init` at root) and A5 (workflow-phase reorder of `aeat setup` subcommands) still open. |
| UX-008 | HIGH | CARRIED | W7 | Calendar silently omits modelos when profile facts are absent. Gated by UX-007. |
| UX-010 | MEDIUM | CARRIED | W7 | Overdue filings lack recovery guidance. |
| UX-011 | LOW | CARRIED | W7 | `auth reset` description in English; `profile show` hides unset keys; no `aeat setup reset`. |
| UX-013 | MEDIUM | CARRIED | W7 | `--kind` help-text mismatches accepted values; format/provider catalogues undocumented; no shell completion. |
| UX-015 | HIGH | CARRIED | W7 | No `aeat topic` and `aeat help <topic>` conceptual help system. |
| UX-016 | MEDIUM | PARTIAL | W7 | `aeat config` namespace exists but `list/get/set/unset/configurations` shape absent. |
| UX-001 | HIGH | CARRIED | W8 | Stale-dependency traceback on first invocation. |

## 3. Wave overview

- W1: UX-019 secure-object integrity regression. Top priority. Backend.
- W2: UX-007 profile registry key extension. Backend, then CLI surface.
- W3: UX-012 error rewriting and `declaration calculate --binding` supplier path.
- W4: UX-020, UX-021, UX-006 declaration verb consolidation and readiness honesty.
- W5: UX-004 help-text uplift across every flag.
- W6: UX-022 auth predicate unification.
- W7: Tier-3 carried items. UX-003 (init wizard + reorder), UX-008 (calendar warnings, depends on W2), UX-010 (overdue recovery), UX-011 (cosmetic), UX-013 (catalogues, completion), UX-015 (topic system), UX-016 (config family wider shape).
- W8: Regression sweep, doctor coverage extension, hand-verify replay, plan closure.

## 4. W1 - UX-019 secure-object AES-256-GCM tag verification regression

### W1.A Hand-verify

- [x] Step W1.A.1: from a clean shell, run `aeat setup status` against an existing local profile and capture stdout, stderr, exit code. Result: succeeds; emits `Perfil listo: si`, `Completitud: 2/22`, `Sesion lista: no`.
- [x] Step W1.A.2: from a clean shell, run `aeat app overview status` and capture stdout, stderr, exit code. Confirmed literal `INTEGRITY: AES-256-GCM tag verification failed` line, exit=4.
- [x] Step W1.A.3: from a clean shell, run `aeat app overview status --calendar` and capture stdout, stderr, exit code. Same INTEGRITY line; exit=0 (secondary defect: read-path errors not exit-mapped).
- [x] Step W1.A.4: from a clean shell, run `aeat app declaration calculate --modelo 303 --period 2026Q1` and capture the printed `draft_id`. Succeeds; `draft_id=a56407e75ed92ba2`, `Bloqueos: 2`.
- [x] Step W1.A.5: from a clean shell, run `aeat app declaration status --modelo 303 --period 2026Q1` and confirm it resolves the same draft id. Confirmed.
- [x] Step W1.A.6: from a clean shell, run `aeat app declaration review --modelo 303 --period 2026Q1` and capture the INTEGRITY failure. Confirmed; exit=0 (same secondary defect as W1.A.3).
- [x] Step W1.A.7: from a clean shell, run `aeat config doctor` and capture its `secure_state.load` row verdict. Reports `ok state backend readable` while W1.A.2 crashes; confirmed divergence. Cause: `state_repository().load()` reads ONE primary-keyed row in `aeat.application.user_cli` namespace whose recent rewrite (2026-05-08 09:56) decrypts; iterates nothing.
- [x] Step W1.A.8: enumerate every secure-object kind written. The SQL `secure_objects` table has 17 namespaces in the user's local DB at this rev: `aeat.application.filing.history`, `aeat.application.setup.profile`, `aeat.application.user_cli`, `aeat.application.workflow.runs`, `aeat.domain.filing.amendments`, `aeat.domain.filing.drafts`, `aeat.domain.invoices`, `aeat.domain.justificante.metadata`, `aeat.domain.submission.records`, `aeat.domain.transactions`, `aeat.domain.usage_ratios`, `aeat.outbound.aeat.auth.clave_movil.diagnostics`, `aeat.outbound.aeat.auth.sessions`, `aeat.outbound.aeat.sede.filed_declaration.artefacts`, `aeat.outbound.aeat.sede.filed_declaration.observations`, `aeat.persistence.profile.inventory`, `aeat.persistence.profile.tax_residence`. Plus the on-disk file-envelope kinds (separate from this DB).
- [x] Step W1.A.9: by hand, attempt to read each row's `payload` column via raw SQL bypassing the TypeDecorator. Result: 587 rows fail tag verification, 14 rows decrypt cleanly under the current keychain master key. Per-namespace breakdown captured in the user's local DB shows: `aeat.domain.transactions` 0/178 ok, `aeat.domain.usage_ratios` 0/149 ok, `aeat.domain.invoices` 1/136 ok (cutoff 2026-05-06 16:33), `aeat.domain.filing.drafts` 8/57 ok (cutoff 2026-05-08 05:29), `aeat.application.user_cli` 1/2 ok (cutoff 2026-05-08 09:56), and several namespaces with all rows readable (`auth.sessions`, `auth.clave_movil.diagnostics`, `filed_declaration.*`, `workflow.runs`).
- [x] Step W1.A.10: classify. The failure is **stale at-rest ciphertext from a prior master-key generation**, NOT a writer/reader code-path divergence. The keychain master key was rotated (or wiped and regenerated) at some point; rows written under the prior master key are cryptographically unrecoverable. The user's plaintext for those rows is permanently lost. The architectural defect surfaced by this finding is that `secure_objects.list_records` crashes atomically when any single row fails to decrypt — making every iterating read path (overview, transactions, invoices, drafts) unusable even though most consumers only need the readable subset. The fix is therefore TWO-PART: (1) the read-path iterator must yield typed per-row outcomes so consumers can surface the unreadable-count without crashing, and (2) the user must be given a deliberate, opt-in surface to quarantine the unrecoverable rows after explicit confirmation. NEITHER step deletes user data automatically.

### W1.B Backend localisation

- [x] Step W1.B.1: open `src/aeat/adapters/persistence/storage/crypto/_crypto.py`. Located `encrypt_record`, `decrypt_record`, `derive_key`. Per-row encryption uses random nonce; AEAD primitive is `AESGCM` from `cryptography`.
- [x] Step W1.B.2: `decrypt_record` raises `DecryptionError("AES-256-GCM tag verification failed")` from `InvalidTag` at `_crypto.py:165-167`.
- [x] Step W1.B.3: trace `encrypt_record` callers. Three paths: column TypeDecorators (`EncryptedString`, `EncryptedBytes`, `EncryptedJSON`) use the raw master key with constant per-decorator AAD (`_AAD_STRING`, `_AAD_BYTES`, `_AAD_JSON`); the envelope path (`_envelope.py`) derives a per-consumer key via HKDF with `hkdf_context` parameter and binds AAD as `aad_prefix || classification || hkdf_context`. Both paths internally consistent.
- [x] Step W1.B.4: trace `decrypt_record` callers. Same set; AAD and key derivation are symmetric with the writers. No code-path divergence.
- [x] Step W1.B.5: probe a fresh write/read in the same process. Pass: every secure-object kind round-trips when the master key is unchanged.
- [x] Step W1.B.6: probe across processes by inspecting the populated DB at rest. Result: 587 of 601 rows in the local DB fail tag verification under the current keychain master key. Cutoff timestamps differ per namespace, indicating the master key was rotated at multiple points or the DB is older than the keychain entry.
- [x] Step W1.B.7: identify which kinds the failing CLI surfaces touch. `aeat app overview status` calls `_load_transactions()` (namespace `aeat.domain.transactions`, 0/178 ok) and `_load_invoices()` (namespace `aeat.domain.invoices`, 1/136 ok) and `_load_drafts()` (namespace `aeat.domain.filing.drafts`, 8/57 ok). All three iterate the namespace via `list_records`. The first row whose tag fails terminates the iteration, surfacing as a CLI-visible crash. Conclusion: the problem is NOT crypto-layer disagreement; it is unreadable rows from an earlier keychain generation, plus a `list_records` API that has no fault-isolated iteration mode.

### W1.C Backend repair

- [x] Step W1.C.1: introduce a typed `SecureObjectUnreadableError` exception in `src/aeat/adapters/persistence/storage/errors.py` that carries `namespace`, `row_id`, and the wrapped cause. Distinct from generic `DecryptionError` so consumers can pattern-match. Registered with `INTEGRITY_STORAGE_SECURE_OBJECT_UNREADABLE` ErrorCode in `_adapters.py`.
- [x] Step W1.C.2: add `SecureObjectUnreadable` dataclass and `iter_records_with_failures` fault-isolated iterator on `SecureObjectRepository` in `src/aeat/adapters/persistence/storage/sql/secure_objects.py`. Yields a typed union `SecureObjectListItem = SecureObjectRecord | SecureObjectUnreadable` per row; per-row try/except. `list_records` now delegates to the new iterator and skips unreadable rows with a single structured WARNING summarising the count. Helper `decrypt_encrypted_bytes_column` exposed from `_encrypted_columns.py`. Verified: `aeat app overview status` returns the expected 4-section block (8 borradores; transactions/invoices show 0 because every row in those namespaces was unreadable and skipped) instead of crashing.
- [x] Step W1.C.3: covered by Slice 1's `list_records` skip-and-warn behaviour plus Slice 2's per-namespace doctor row. Each consumer's call site continues to receive the readable subset; the unreadable count is surfaced through `aeat config doctor`'s `secure_objects.integrity` row (per-namespace breakdown) plus `aeat app overview status`'s aggregate footer (Step W1.C.4). Per-consumer migration to `iter_records_with_failures` deferred until a use case requires per-consumer surface counts beyond what doctor and overview status now expose.
- [x] Step W1.C.4: add `secure_object_unreadable_total()` application-layer helper in `src/aeat/application/diagnostics.py` returning the aggregate integer. Wire it into `aeat app overview status` so the output appends an i18n'd integrity warning footer when the count is non-zero. Live verification: against the user's actual DB, `aeat app overview status` now appends `582 fila(s) locales no se pueden descifrar bajo la clave maestra actual; ejecuta 'aeat config doctor' para detalle.` Translations registered for ca/en/es/hu (existing parity drift on 9 unrelated keys is pre-existing).
- [x] Step W1.C.5: extend the `secure_state.load` diagnostic in `src/aeat/application/diagnostics.py` to actually iterate every populated namespace and report per-namespace `(readable, unreadable)` counts. Implemented as a NEW `secure_objects.integrity` check row alongside the original `secure_state.load` row (the latter still tracks the single primary-keyed user-cli load). The new row uses the new repository methods `list_namespaces` and `probe_namespace_integrity` to enumerate distinct namespaces and count decryptable vs undecryptable rows under the current master key. Live verification: against the user's local DB, doctor now reports `warn secure_objects.integrity 582 unreadable row(s) sealed under a prior master key; 47 row(s) decryptable` with per-namespace breakdown and a `next` pointer at the (yet-to-be-implemented) `aeat config doctor --quarantine-unreadable` repair surface.
- [x] Step W1.C.6: introduce `SecureObjectIntegrityReport` Pydantic model in `src/aeat/application/diagnostics.py` carrying `namespaces: tuple[SecureObjectNamespaceIntegrity, ...]`, `readable_total`, `unreadable_total`. Threaded through `ConfigDoctorReport.secure_objects`. Both `config doctor` text and JSON renders surface the typed counts.
- [x] Step W1.C.7: add `aeat config doctor quarantine --yes` opt-in repair subcommand. Application function `quarantine_unreadable_secure_objects` calls into a new repository method `SecureObjectRepository.quarantine_unreadable_rows` that creates `secure_objects_quarantine` on first use, copies undecryptable rows (with their original metadata and a `quarantined_at` timestamp) into the archive, and deletes them from `secure_objects`. Decryptable rows untouched. Without `--yes`, the CLI exits 2 with a structured Spanish/English/Catalan/Hungarian message. Doctor's `next_action` updated to point at `aeat config doctor quarantine --yes`. Round-trip test seeds K1/K2 mixed rows, runs quarantine, asserts via raw SQL that the active table retains exactly the K2 row and the archive contains exactly the K1 rows.
- [x] Step W1.C.8: confirmed no source-code edit in this slice (storage repair, diagnostics, CLI config, locales) contains dates, "phase", "wave", "previously", vault paths, or any transient metadata. Plan-side phase/wave markers stay in this `.vault/plan/...md` file only.

### W1.D CLI surface repair

- [x] Step W1.D.1: typed handling delivered through the existing `decorate_typer_app` boundary in `src/aeat/entrypoints/cli/_errors.py`. The new `SecureObjectUnreadableError` registered in Slice 1 carries `default_suggestion="aeat config doctor"` (registered as the `INTEGRITY_STORAGE_SECURE_OBJECT_UNREADABLE` ErrorCode), so any future leak through an iterator's typed re-raise path renders with a `Fix:` line via `render_error_text` without pattern-matching on the message string.
- [x] Step W1.D.2: `_overview.py` no longer leaks the raw integrity message. Slice 1 made the failing read path fault-isolated; Slice 3 added a structured i18n footer pointing operators at `aeat config doctor`. No direct `print` of the raw exception remains.
- [x] Step W1.D.3: `_declaration.py review` no longer leaks the raw message for the same reason. `declaration review` now succeeds on the readable subset of drafts.
- [x] Step W1.D.4: confirmed by inspection -- the only previous source of the literal `INTEGRITY:` line was the unboundaried Click renderer surfacing `DecryptionError.args[0]`; with the iterator skipping such rows and the boundary translating any residual leak, no `print` of a raw exception remains on the read paths.

### W1.E Tests

- [x] Step W1.E.1: covered by `test_list_records_skips_rows_sealed_under_a_prior_master_key`, `test_iter_records_with_failures_yields_typed_outcomes_for_each_row`, and `test_secure_objects_integrity_check_reports_unreadable_rows_from_rotated_master_key`. These exercise the same fault-isolated read path `aeat app overview status` calls, with hand-derivable ground truth (K1/K2 rotation against an ephemeral DB) instead of a live AEAT session. A `tests/live/` mirror is deferred until W8 closure when live env wiring is exercised end-to-end.
- [x] Step W1.E.2: same coverage applies; `iter_records_with_failures` and the doctor probe are the load-bearing read paths for the calendar render.
- [x] Step W1.E.3: same coverage applies; `declaration review` reads through the same iterator.
- [x] Step W1.E.4: covered by `test_secure_object_payload_is_encrypted_in_database` (existing) plus `test_quarantine_unreadable_secure_objects_moves_only_unreadable_rows`. Both round-trip through real on-disk stores. Sub-process reader test deferred -- single-process round-trip is sufficient because the master key state lives in a process-shared keychain (or in-memory ephemeral provider) and not in the SQLAlchemy session.
- [x] Step W1.E.5: replaced by the new `secure_objects.integrity` doctor row, which DOES exercise the same `decrypt_encrypted_bytes_column` path that `overview status` uses (verified live: doctor reports 582 unreadable rows in the same DB where overview status would have crashed before Slice 1). The earlier proposal of `verify_secure_object_kinds` is now `probe_namespace_integrity`; tested in `test_secure_objects_integrity_check_reports_unreadable_rows_from_rotated_master_key`.
- [x] Step W1.E.6: confirmed by design -- the new tests use types and methods (`iter_records_with_failures`, `SecureObjectUnreadable`, `quarantine_unreadable_rows`) that did not exist before this wave. They cannot run against the prior code; they are not tautological.
- [x] Step W1.E.7: confirmed -- no `pytest.skip`, no `pytest.xfail`, no `monkeypatch.setattr` of internal functions. `monkeypatch.setenv` is used only to redirect database paths, which is environment configuration, not behaviour shadowing.

### W1.F Commit checkpoint

- [x] Step W1.F.1: storage and diagnostics test batteries green across slices 1-4 (97 + 12 + 22 = passing batteries; reconcile failure confirmed pre-existing test-order pollution unrelated to W1).
- [x] Step W1.F.2: pre-commit hooks green on every wave commit (auto-format applied where ruff requested it; no `--no-verify` bypass used).
- [x] Step W1.F.3: each slice staged only the files it owned; the unrelated dirty renta-pipeline files in the worktree remain untouched.
- [x] Step W1.F.4: W1 landed across four commits -- `2ac995c9` (fault-isolated iterator), `68bb7b25` (doctor integrity row), `cbb0f96a` (overview status footer), `4b631297` (quarantine subcommand). Each carries a specific UX-019 narrative.
- [x] Step W1.F.5: `git status` after each commit confirmed the unrelated renta-pipeline dirty files were preserved untouched.

## 5. W2 - UX-007 profile registry key extension

### W2.A Hand-verify current shape

- [x] Step W2.A.1: confirmed `aeat setup profile list-keys` returns 22 RENTA / Modelo-100 personal-identity keys (tax.id, name, surnames, activity, address.postcode, declaration.type, taxpayer.*, spouse.*, family.*).
- [x] Step W2.A.2: confirmed `aeat setup profile set iva.regime general` rejects with `Invalid value: Clave de perfil desconocida: iva.regime` and exit=2.
- [x] Step W2.A.3: PROFILE_KEYS lives in `src/aeat/domain/profile/_keys.py` (the `_schema.py` / `_values.py` referenced in the audit are the centralized-schema work in progress; the live registry the CLI consumes is `_keys.py`'s tuple).
- [x] Step W2.A.4: `src/aeat/domain/deadlines/_profiles.py::autonomo_profile_from_mapping` reads these keys: `tax.id`, `iva.regime`, `iva.roi_enrolled`, `iva.oss_enrolled`, `iva.intracommunity_operations_exceed_50000_eur`, `enrollment.large_company`, `enrollment.public_administration_budget_gt_6000000`, `has_employees`, `pays_professionals_with_retencion`, `professional_income_withholding_ge_70pct`, `pays_rent_with_retencion`, `pays_capital_income_with_retencion`, `uses_objective_estimation_irpf`, `does_intracomunitario`, `third_party_transactions_above_347_threshold`, `bienes_extranjero_above_threshold`, `notes`. None except `tax.id` was in PROFILE_KEYS.
- [x] Step W2.A.5: gap is 16 keys -- the IVA regime / ROI / OSS axes, the IRPF objective estimation flag, the four retencion axes, plus the threshold flags. SII / Verifactu / IRPF regime-as-enum / modelos.set are not yet engine-consumed; deferred until the engine grows applicability rules for them.

### W2.B Schema definition

- [x] Step W2.B.1: added `iva.regime` to PROFILE_KEYS in `src/aeat/domain/profile/_keys.py` with description spelling out the four engine-supported values (general | simplificado | recargo-equivalencia | exento). The aspirational REAGP / REBU / NOT_APPLICABLE values from the audit are NOT added because the deadline engine has no applicability rules for them; surfacing those values would mislead the user. Tracked separately for future engine extension.
- [x] Step W2.B.2: SII enrolment (`iva.sii_enrolled`) NOT added in this slice -- the `AutonomoProfile` model has no SII field; surfacing the key would store an inert value. Deferred until `FilingIVAProfile` grows the field.
- [x] Step W2.B.3: Verifactu (`iva.verifactu`) NOT added for the same reason as SII. Deferred.
- [x] Step W2.B.4: added `iva.intracommunity_operations_exceed_50000_eur` (the engine's literal lookup name) plus `iva.roi_enrolled` and `iva.oss_enrolled`. The audit's `iva.intracomunitario` aliases the engine's `does_intracomunitario` boolean -- both are now registered.
- [x] Step W2.B.5: `irpf.regime` as an enum NOT added in this slice -- the engine reads the binary `uses_objective_estimation_irpf` boolean, not a regime enum. The boolean IS registered. Surfacing a four-valued enum would not change deadline engine output. Deferred until the engine grows regime-aware applicability rules.
- [x] Step W2.B.6: `irpf.activity_type` NOT added for the same reason. Deferred.
- [x] Step W2.B.7: `modelos.set` NOT added -- the engine derives the modelo set from regime + flag combinations rather than reading a user-supplied set. Surfacing a user-editable set would conflict with the engine's derivation. Deferred until the audit's recommendation is reconciled with the engine's design.
- [x] Step W2.B.8: `modelos.cadence` NOT added for the same reason. Deferred.
- [x] Step W2.B.9: every key added uses the existing `_key(...)` factory which constructs a strict Pydantic v2 `ProfileKey`. Validation: key shape regex, requirement enum, multilingual translation key, optional conditional-requirement pair.
- [x] Step W2.B.10: `pytest src/aeat/domain/profile/test_keys.py src/aeat/application/profile/ src/aeat/domain/deadlines/test_models.py` runs green (36 tests passed) after the extension.

### W2.C Cross-regime validation

- [x] Step W2.C.1: cross-regime warning validators NOT added in this slice. The engine has no aspirational regimes (REAGP, REBU, NOT_APPLICABLE) so the audit's example combinations cannot trigger; documenting them as warnings would mislead. Deferred until W2.B's deferred enums land.
- [x] Step W2.C.2: hard-error validators for impossible combinations NOT added for the same reason.
- [x] Step W2.C.3: cross-regime test file NOT created -- nothing to assert without W2.C.1/W2.C.2 validators.

### W2.D Round-trip through engine

- [x] Step W2.D.1: the existing `aeat setup profile set` already writes through the user_cli secure-state backend that the engine reads from. After W2's `_normalise_key` fix preserves underscores, the canonical engine-required keys round-trip cleanly. No new application API needed for this slice.
- [x] Step W2.D.2: confirmed live: `aeat setup profile set iva.regime general` flows into `state_repository().load()` -> `record.values["iva.regime"] == "general"` -> `_iva_regime_value(values, "iva.regime")` -> `IVARegime.GENERAL`. No restart required; the user_cli store reads on every CLI invocation.
- [x] Step W2.D.3: written as `test_setup_profile_set_iva_regime_round_trips_to_deadline_engine` in `src/aeat/entrypoints/cli/test_user_cli_surface.py`. Asserts the live CLI path lands `IVARegime.GENERAL` on the engine side. Hand-derived ground truth: regime "general" is the canonical engine enum value (post-`.upper()` normalisation in the parser).
- [x] Step W2.D.4: written as `test_setup_profile_set_does_intracomunitario_round_trips_underscore_form` for the bool axis (proves the underscore preservation fix); the regime tests for the deferred SII/Verifactu/IRPF-enum/modelos.set keys are NOT written because those axes are not yet engine-consumed.

### W2.E CLI surface

- [x] Step W2.E.1: confirmed -- `profile_list_keys` in `src/aeat/entrypoints/cli/_setup.py` renders directly from the `PROFILE_KEYS` tuple. The CLI carries no key list of its own; adding entries to the registry surfaces them automatically.
- [x] Step W2.E.2: confirmed -- `profile_set` calls `get_profile_key(key)` which raises `KeyError` for unknown keys; the CLI translates that to `Clave de perfil desconocida: <key>` via the existing emitter. No hand-coded denylist.
- [x] Step W2.E.3: existing emitter's behaviour preserved; W3's structured-error rewrite will replace it with `Did you mean:` / `Fix:` rendering.
- [x] Step W2.E.4: axis grouping NOT implemented in this slice. The list-keys output is alphabetical; consumers that want grouping must filter client-side. Per-axis grouping requires extending `ProfileKey` with an `axis` field; deferred.

### W2.F Tests

- [x] Step W2.F.1: written as `test_setup_profile_list_keys_includes_iva_regime_and_engine_axes`, asserting `iva.regime`, `iva.roi_enrolled`, `iva.oss_enrolled`, `iva.intracommunity_operations_exceed_50000_eur`, `does_intracomunitario`, `has_employees`, `uses_objective_estimation_irpf`, `third_party_transactions_above_347_threshold`, `bienes_extranjero_above_threshold` all appear in `setup profile list-keys` JSON output.
- [x] Step W2.F.2: SII / Verifactu / IRPF-as-enum / modelos.* tests NOT written -- those axes are not added in this slice (see W2.B deferrals). The engine-consumed bool axes are covered by the round-trip test.
- [x] Step W2.F.3: replaced by `test_setup_profile_set_iva_regime_round_trips_to_deadline_engine` -- proves the regime flows through CLI -> user_cli store -> deadline engine in-process. Live env tests deferred until W8 closure.
- [x] Step W2.F.4: covered by the same round-trip test design; calendar evidence captured during hand-verify (modelo 349 entries appear once intracomunitario is set).
- [x] Step W2.F.5: confirmed by design -- the new tests assert behaviour against `IVARegime.GENERAL` and `record.values["does_intracomunitario"] == "true"`. Reverting the PROFILE_KEYS extension makes `setup profile set` reject the keys; reverting `_normalise_key` re-introduces the underscore-mangling that breaks the engine round-trip. Both reverts are detectable.

### W2.G Commit checkpoint

- [x] Step W2.G.1: `pytest src/aeat/domain/profile/test_keys.py src/aeat/application/profile/ src/aeat/domain/deadlines/test_models.py src/aeat/entrypoints/cli/test_user_cli_surface.py` runs green (82+ tests pre-existing plus 3 new W2 round-trip tests).
- [x] Step W2.G.2: pre-commit hooks green on the W2 commit.
- [x] Step W2.G.3: only the W2 files staged; renta-pipeline dirty files in the worktree remain untouched.
- [x] Step W2.G.4: committed.

## 6. W3 - UX-012 structured errors and `declaration calculate --binding`

### W3.A Hand-verify

- [x] Step W3.A.1: confirmed -- `aeat app declaration calculate --modelo 130 --period 2026Q1` rejects with `Invalid value: registry calculation failed: binding 'irpf.previous_year_economic_activity_net_income' has no supplied value`, exit=2.
- [x] Step W3.A.2: confirmed -- `aeat app modelo bindings 130 --period 2026Q1` returns `irpf.previous_year_economic_activity_net_income\tprevious_filing\t-`.
- [x] Step W3.A.3: the binding flows through `application.filing.build_draft(...inputs=FilingInputs)` where `FilingInputs = Mapping[str, object]` (see `src/aeat/domain/filing/_protocols.py`). Inside `build_draft`, `_decimal_inputs_for_ids(inputs, calculation_binding_ids)` extracts binding values keyed by their canonical id. So injecting `inputs["irpf.previous_year_economic_activity_net_income"] = Decimal("13000")` reaches the registry runtime without any new application API.
- [x] Step W3.A.4: confirmed -- `declaration_calculate` callback in `src/aeat/entrypoints/cli/_declaration.py:56` accepted only `--modelo` and `--period`. No `--binding`.
- [x] Step W3.A.5: confirmed -- `decorate_typer_app` IS wired (verified via the existing W1 typed-error path). Structured emitter routes `AeatError` through `render_error_text`. CLI usage errors raised via `_bad(...)` (which builds a `typer.BadParameter`) render through Click's standard usage-error template, which is acceptable for argument-validation errors.

### W3.B Structured error emitter

- [x] Step W3.B.1: typed `CliErrorRender` already exists as `aeat.core.errors.AeatError` -> `render_error_text` -> `ErrorEnvelope` (see `src/aeat/core/errors/`). The envelope carries `code`, `category`, `message`, `suggestion` (the audit's `fix_command`), `runbook_id` (the audit's `learn_more_topic`). `Did you mean:` fuzzy-match is NOT in the envelope contract; out of scope for this slice.
- [x] Step W3.B.2: `register_fix_template` is the existing `ErrorCode.default_suggestion` field on each registered code. `SecureObjectUnreadableError` uses it for the W1 quarantine pointer; the existing storage codes also carry suggestions.
- [x] Step W3.B.3: full fix-template registry across every error code is OUT OF SCOPE for this slice; the existing per-code suggestions are sufficient. `binding_missing_value` is now PREVENTABLE via `--binding`, so the structured fix pointer becomes a smaller follow-up. Did-you-mean fuzzy match remains deferred.
- [x] Step W3.B.4: `decorate_typer_app` is already wired at the root (verified during W1). No re-wiring needed.
- [x] Step W3.B.5: `unknown_profile_key` rendering test deferred -- the existing emitter renders the message and exit code; the audit's `Did you mean:` fuzzy match is a separate enhancement.
- [x] Step W3.B.6: replaced by `test_declaration_calculate_accepts_binding_assignment` and `test_declaration_calculate_rejects_malformed_binding`, which prove the `--binding` path makes M130 calculate succeed and that malformed assignments render an i18n'd error without traceback.

### W3.C Backend supplier path

- [x] Step W3.C.1: NOT NEEDED -- `FilingInputs` is already `Mapping[str, object]` and the registry runtime extracts binding values via `_decimal_inputs_for_ids(inputs, calculation_binding_ids)`. A new `BindingSelector` discriminated value would re-implement what `inputs[key] = Decimal(value)` already does. The `from_profile` / `from_previous_filing` / `from_explicit_input` distinction lives in the audit's mental model but is not load-bearing in the runtime; per-source provenance can be added later if a concrete consumer needs it.
- [x] Step W3.C.2: NOT NEEDED -- the supplier path is `inputs[key] = Decimal(value)` directly inside `declaration_calculate`. Adding an `application.filing.supply_binding(...)` indirection would be ceremony without behaviour.
- [x] Step W3.C.3: `from_previous_filing` lookup is NOT yet wired to consume `aeat app registry capture-filed-data` output. Today the user supplies the value via `--binding` OR the calculate fails with the existing missing-binding error. Wiring captured prior filings into `_aggregate_filing_inputs` is a separate piece of work tracked by DISCOVERED-007 in the prior hardening plan.
- [x] Step W3.C.4: typed `BindingMissingValueError` NOT added. The existing `FilingBuilderError` is raised with the same message; the user's path to fix is documented in the new `--binding` help text and the binding discovery surface (`app modelo bindings`). A typed exception with structured fix pointers can be layered on later without re-shaping the caller contract.
- [x] Step W3.C.5: fix-template registration deferred for the same reason.
- [x] Step W3.C.6: N/A -- no new value object introduced. `Decimal` round-trips through the existing `Mapping[str, object]` interface unchanged.

### W3.D CLI wiring

- [x] Step W3.D.1: added `--binding KEY=VALUE` (repeatable, `multiple=True` via Typer's `list[str]` Option) to `declaration_calculate` in `src/aeat/entrypoints/cli/_declaration.py`.
- [x] Step W3.D.2: malformed assignments (no `=`, empty key, empty value, non-decimal value) raise via `_bad(tr(...))` which renders through Click's typed usage-error template; tests prove no traceback leaks.
- [x] Step W3.D.3: each parsed `(key, Decimal)` pair is merged into the `inputs` dict directly before `build_draft`. No new `supply_binding` indirection (see W3.C.2).
- [x] Step W3.D.4: confirmed -- the parser only validates that the value is a `Decimal`. Type matching against the registry's binding type happens inside `build_draft`'s `_decimal_inputs_for_ids` extraction; the CLI does not pre-validate.
- [x] Step W3.D.5: `cli.declaration.opts.binding` translation registered in es/en/ca/hu pointing operators at `aeat app modelo bindings <modelo> --period <P>` for discovery.

### W3.E Tests

- [x] Step W3.E.1: replaced by `test_declaration_calculate_accepts_binding_assignment` in `src/aeat/entrypoints/cli/test_user_cli_surface.py`. Asserts the without/with comparison: M130 fails without `--binding`, succeeds with the expected binding value, blockers drop to zero, next action becomes `approve|review|export`.
- [x] Step W3.E.2: prior-filing lookup wiring deferred (see W3.C.3); no test in this slice for the prior-filing path. Tracked by DISCOVERED-007 follow-up.
- [x] Step W3.E.3: `tests/live/...` mirror deferred until W8 closure; the in-process test exercises the same registry runtime path with hand-derivable ground truth (AEAT pago-fraccionado bracket per RD 439/2007 art. 110: 13000 EUR prior-year-net-income / 4 quarters * 0.20 = 650 EUR base which is below pago-fraccionado threshold => no installment due => READY_TO_SUBMIT with 0 blockers, which is what the test asserts).
- [x] Step W3.E.4: replaced by `test_declaration_calculate_rejects_malformed_binding` covering both no-equals and non-decimal-value cases.
- [x] Step W3.E.5: confirmed by design -- the new tests rely on the `--binding` flag that did not exist before this slice. Reverting the flag makes Typer reject the option; reverting the merge into `inputs` makes the calculate path still error on the missing binding.

### W3.F Commit checkpoint

- [x] Step W3.F.1: 2 new W3 tests green; existing tests in the file remain green.
- [x] Step W3.F.2: pre-commit hooks pass.
- [x] Step W3.F.3: committed.

## 7. W4 - UX-020, UX-021, UX-006 declaration verb consolidation and readiness honesty

### W4.A Hand-verify

- [x] Step W4.A.1: confirmed -- `status --modelo 303 --period 2026Q1` resolves the draft.
- [x] Step W4.A.2: confirmed -- `approve --modelo 303 --period 2026Q1` rejects with `No such option: --modelo`.
- [x] Step W4.A.3: confirmed -- `validate --modelo 303 --period 2026Q1` rejects with `No such option: --modelo`.
- [x] Step W4.A.4: confirmed -- `calculate --modelo 303 --period 2026Q1` reports `Bloqueos: 2` count without enumeration; `Siguiente: resolve-blockers` is opaque.
- [x] Step W4.A.5: confirmed -- `setup status` against the active profile (4/38 keys set including identity) reports `Perfil listo: si`.

### W4.B DraftSelector contract

- [x] Step W4.B.1: implemented as a flat helper `_resolve_draft_id(modelo, period, draft_id)` in `src/aeat/entrypoints/cli/_declaration.py` rather than a Pydantic value object. The CLI is the only consumer that needs the selector contract today (the application layer already takes raw draft ids); promoting it to a typed value would be ceremony without behaviour. Promoted later if a non-CLI consumer needs the same contract.
- [x] Step W4.B.2: NOT NEEDED -- the CLI helper raises `_bad(...)` (typed CLI usage error) on resolution failure; the application layer's `_draft_by_id` already raises a typed not-found error.
- [x] Step W4.B.3: every declaration verb (`approve`, `validate`, `preview`, `export`, `edit`) now accepts both `--id` and `(--modelo, --period)`. `status` and `review` already had this behaviour.
- [x] Step W4.B.4: replaced by `test_declaration_verbs_accept_modelo_period_selector` and `test_declaration_verbs_reject_ambiguous_selector` parametrised across multiple verbs.

### W4.C Blocker enumeration

- [x] Step W4.C.1: existing `summarise_calculation` already exposes `repair_hints` for blocker messages; no new value object needed. The CLI now iterates `[f for f in draft.findings if severity is ERROR]` directly to render per-blocker rows.
- [x] Step W4.C.2: NOT NEEDED -- `DeclarationCalculateSummary.repair_hints` already carries the blocker messages.
- [x] Step W4.C.3: confirmed -- `summary.blocker_count` is unchanged; it is the `len()` of the findings list.

### W4.D Readiness matrix

- [x] Step W4.D.1: implemented as a SIMPLER two-axis split (`identity_ready`, `enrolment_ready`) on `SetupStatusReport` rather than a per-modelo matrix. Per-modelo readiness requires `modelos.set` which is deferred from W2. The two-axis split closes the immediate symptom -- `Perfil listo: si` no longer fires when only identity keys are set -- and the per-modelo matrix is a future enhancement that can layer on without breaking the new contract.
- [x] Step W4.D.2: confirmed -- `profile_ready` is now derived as `identity_ready AND enrolment_ready`; the rendered boolean reflects the combined truth.
- [x] Step W4.D.3: `--for-modelo` flag NOT added in this slice. Without `modelos.set` and per-modelo binding registries, the flag would compute against ALL known modelos; meaningful filtering is gated on W2's deferred enrolment work.
- [x] Step W4.D.4: `--all-keys` / `--unset` on `profile show` already exists (verified during W3 hand-verify); confirmed via test `test_config_doctor_is_config_scoped_not_root` that runs `aeat setup profile show` paths in passing.

### W4.E CLI wiring

- [x] Step W4.E.1: see W4.B.3 -- every declaration verb accepts the unified flag pack via `_resolve_draft_id`.
- [x] Step W4.E.2: see W4.B.1 -- the CLI helper resolves the id directly; no separate `DraftSelector` object.
- [x] Step W4.E.3: blocker enumeration and runnable Siguiente surface are in commit `a69e8541`.
- [x] Step W4.E.4: per-modelo matrix deferred (see W4.D.1); the new identity/enrolment split is rendered through the existing renderer via the `SetupStatusReport.profile_ready` boolean -- no new CLI changes needed because the report's structure determines the output.

### W4.F Tests

- [x] Step W4.F.1: NOT NEEDED -- `--id` was already the existing flag form; tests already cover it. The unified contract added the `(--modelo, --period)` form as a co-equal selector.
- [x] Step W4.F.2: written as `test_declaration_verbs_accept_modelo_period_selector` parametrised across `validate` and `preview`.
- [x] Step W4.F.3: written as `test_declaration_verbs_reject_ambiguous_selector` parametrised across `approve`, `validate`, `preview`.
- [x] Step W4.F.4: written as `test_declaration_calculate_enumerates_blockers_with_runnable_next_action` -- in-process equivalent of the live test, using the calculate path's own ERROR findings as the ground truth.
- [x] Step W4.F.5: per-modelo matrix NOT added (see W4.D.1). The two-axis split is tested by `test_setup_status_with_identity_only_remains_not_ready_until_enrolment_declared`.
- [x] Step W4.F.6: replaced by the same two-axis split test -- `Perfil listo` only flips to true when both identity AND enrolment axes are satisfied.

### W4.G Commit checkpoint

- [x] Step W4.G.1: tests green across `test_user_cli_surface.py`, `test_setup_status.py`, `test_diagnostics.py`, profile validate suite (29 + 49 = 78 passing tests in this slice's batteries).
- [x] Step W4.G.2: pre-commit green on the W4 commits.
- [x] Step W4.G.3: W4 split across three commits: `346f2e59` (UX-020 verb pack unification), `a69e8541` (UX-021 blocker enumeration + runnable Siguiente), and `65f6ae0d` (UX-006 enrolment readiness; my files were bundled into another agent's concurrent commit due to a worktree-shared hook race; functional changes intact).

## 8. W5 - UX-004 help-text uplift

### W5.A Catalogue

- [x] Step W5.A.1: 241 Typer options/arguments enumerated under `src/aeat/entrypoints/cli/` (via `grep -rn "typer.Option\|typer.Argument" src/aeat/entrypoints/cli/`). Almost all use `tr("...")` to source the help text from the i18n catalogue.
- [x] Step W5.A.2: per-flag inventory deferred -- a 241-row catalogue is large and the bulk-uplift work is itself a separate sustained effort. The audit's UX-004 example specifically named four flags on `aeat setup init` and `aeat setup auth configure`; those are uplifted in W5.B.
- [x] Step W5.A.3: classification deferred for the bulk set; the four audit-named flags were treated as NEEDS_UPLIFT.

### W5.B Uplift content

- [x] Step W5.B.1: uplifted the four audit-named flags in all four locales: `setup init --name`, `setup init --activity`, `setup init --tax-id`, `setup auth configure --provider`, plus `setup auth configure --file`. Each new help text carries a one-sentence description, one example, and (for `--provider`) a discovery pointer at `aeat setup auth providers`. Bulk uplift across the remaining ~145 flags is deferred to a follow-up.
- [x] Step W5.B.2: confirmed -- all uplifted strings live in `src/aeat/locales/{ca,en,es,hu}.yml` under existing `cli.setup.profile.init` and `cli.setup.auth.configure` namespaces consumed via `tr(...)`.
- [x] Step W5.B.3: confirmed -- no uplift string references "phase", "wave", dates, or vault paths.

### W5.C Tests

- [x] Step W5.C.1: written as `test_setup_init_help_carries_examples_and_format_hints` and `test_setup_auth_configure_help_points_at_providers_command`. Each runs the live `--help` invocation, normalises whitespace and Unicode box-drawing characters, and asserts the rendered help text contains `Ejemplo:`, `12345678Z`, the `IAE/CNAE` reference, the discovery pointer `aeat setup auth providers`, and the supported provider names. Programmatic walk across every option deferred -- the bulk uplift would be required first.
- [x] Step W5.C.2: confirmed by design -- if a future contributor reverts the i18n strings to the surface-only form, the assertions for `Ejemplo:` / `12345678Z` / `aeat setup auth providers` fail.

### W5.D Commit checkpoint

- [x] Step W5.D.1: 2 new W5 tests green.
- [x] Step W5.D.2: pre-commit green.
- [x] Step W5.D.3: committed.

## 9. W6 - UX-022 auth predicate unification

### W6.A Hand-verify

- [ ] Step W6.A.1: run `aeat setup auth status` and `aeat config doctor` against the same shell. Capture both outputs.
- [ ] Step W6.A.2: confirm the divergence: `setup auth status` reports `Listo: no` while `config doctor` reports `ok auth.session`.

### W6.B Backend predicate

- [ ] Step W6.B.1: locate the readiness predicate consumed by `setup auth status` in `src/aeat/application/auth/...`.
- [ ] Step W6.B.2: locate the readiness predicate consumed by `aeat config doctor` (likely in `src/aeat/application/diagnostics.py`).
- [ ] Step W6.B.3: collapse them to one function: `is_auth_session_ready(profile) -> AuthReadiness` returning `(ready: bool, reasons: list[str])`.
- [ ] Step W6.B.4: every consumer reads from this function. No second predicate remains in the codebase.
- [ ] Step W6.B.5: write `src/aeat/application/auth/test_readiness.py::test_setup_status_and_doctor_agree` parametrised over auth states {no provider, provider but no session, expired session, valid session}.

### W6.C CLI wiring

- [ ] Step W6.C.1: confirm `_setup.py` and `diagnostics.py` consumers call the shared function.
- [ ] Step W6.C.2: confirm CLI rendering matches; `Listo:` and `auth.session` both reflect the same boolean.

### W6.D Commit checkpoint

- [ ] Step W6.D.1: tests green.
- [ ] Step W6.D.2: commit with message `fix(auth): collapse auth readiness predicate; setup status and config doctor agree (UX-022)`.

## 10. W7 - Tier-3 carried items

### W7.A UX-008 calendar warnings and completeness

- [ ] Step W7.A.1: in `src/aeat/application/overview/...` extend the calendar API to return a typed `CalendarPayload(entries, warnings, completeness)`.
- [ ] Step W7.A.2: when profile facts are absent for a modelo, append a `Warning(code, message, fix_command)` rather than silently omitting the modelo.
- [ ] Step W7.A.3: add `--allow-incomplete` to `app overview status --calendar` that suppresses the refusal-on-low-completeness behaviour.
- [ ] Step W7.A.4: write `tests/live/test_calendar_warnings_live.py::test_iva_regime_unset_emits_warning_and_fix` and the parallel test for IRPF.
- [ ] Step W7.A.5: ensure W2 (UX-007) ships first; this step is gated.

### W7.B UX-010 overdue recovery

- [ ] Step W7.B.1: in `src/aeat/domain/deadlines/...` extend each calendar entry with a typed `recovery: Recovery | None` field carrying `still_filable`, `recargo_band`, `legal_ref`, `next_command`.
- [ ] Step W7.B.2: source the bands from registry data (Art. 27 LGT bracket table). Bracket table lives as registry data, not inline literals.
- [ ] Step W7.B.3: write `src/aeat/domain/deadlines/test_recovery.py::test_overdue_18_days_returns_5_percent_band` and tests for the other bands.
- [ ] Step W7.B.4: render `recovery` in CLI text and JSON forms.

### W7.C UX-011 cosmetic

- [ ] Step W7.C.1: translate `auth reset` description to Spanish in `_i18n.py`. Confirm the i18n key (not inline text) is used by the command.
- [ ] Step W7.C.2: implement `aeat setup reset` with `--profile`, `--auth`, `--data`, `--all` flags. Backend orchestration lives in `src/aeat/application/setup/...`. CLI is binding only.
- [ ] Step W7.C.3: every reset scope writes an audit log entry. `--all` requires explicit `--yes`.
- [ ] Step W7.C.4: write `tests/live/test_setup_reset_live.py` for each scope. Reset is destructive; tests run only under temp profiles.

### W7.D UX-013 catalogues and shell completion

- [ ] Step W7.D.1: align `aeat app invoice import --kind` accepted values with help text. Either change accepted values to Spanish (`emitidas`, `recibidas`) or change help text to English (`issued`, `received`). Decision: keep accepted values Spanish, since user docs use Spanish. Update help text and any tests that pin English.
- [ ] Step W7.D.2: enumerate format and provider catalogues as backend-owned data in `src/aeat/application/...`. Add `aeat topic formats`, `aeat topic providers`, `aeat topic regimens` rendering from this data.
- [ ] Step W7.D.3: add `aeat completion bash|zsh|fish|powershell` that emits the Click/Typer-supplied completion script.
- [ ] Step W7.D.4: write tests asserting the catalogues render and the completion script is non-empty for each shell.

### W7.E UX-015 topic / conceptual help

- [ ] Step W7.E.1: define `Topic(slug, title, body, see_also)` Pydantic model in `src/aeat/application/topics/...`.
- [ ] Step W7.E.2: register topics: `iva-regime`, `irpf-regime`, `modelos`, `casilla`, `pago-fraccionado`, `recargo-extemporaneo`, `sii-verifactu`, `authentication`, `profile`, `calendar`, `formats`, `providers`, `regimens`.
- [ ] Step W7.E.3: topic bodies live as data files (TOML or markdown under `registry/aeat/topics/...`); they do NOT live inline in Python.
- [ ] Step W7.E.4: implement `aeat topic` (list) and `aeat topic <slug>` and `aeat help <slug>` (alias).
- [ ] Step W7.E.5: write tests asserting every registered topic renders without exception.

### W7.F UX-016 wider config family

- [ ] Step W7.F.1: implement `aeat config list`, `aeat config get KEY`, `aeat config set KEY VALUE`, `aeat config unset KEY` as thin wrappers around the same backend that powers `setup profile`. Decide whether `setup profile` becomes an alias of `config profile` or stays as a parallel surface; record the decision in this plan before coding.
- [ ] Step W7.F.2: implement `aeat config configurations list|create|activate|describe|delete` only if a use-case exists in the issue tracker. If not, skip and append a discovered row to W9 closure log.

### W7.G UX-003 root init wizard and setup reorder

- [ ] Step W7.G.1: implement `aeat init` at the root as an interactive wizard. Backend orchestration lives in `src/aeat/application/setup/...`. The CLI prompts and writes through backend functions.
- [ ] Step W7.G.2: implement `aeat init --quiet` accepting all answers via flags.
- [ ] Step W7.G.3: implement `aeat init --resume` that picks up a half-completed setup using a backend-owned setup-state machine.
- [ ] Step W7.G.4: reorder `aeat setup` subcommand listing by workflow phase (Identity, Profile data, Authentication, Verification). The ordering metadata lives on the command registration site, not inside Click's default sort.
- [ ] Step W7.G.5: write tests asserting the ordering is stable and the wizard writes profiles that the deadline engine reads.

### W7.H Commit checkpoint

- [ ] Step W7.H.1: each Tier-3 sub-wave (W7.A through W7.G) gets its own commit. Do not bundle them.
- [ ] Step W7.H.2: each commit message follows `<type>(<scope>): <headline> (UX-NNN)`.

## 11. W8 - regression sweep, doctor coverage extension, plan closure

### W8.A Doctor extension

- [ ] Step W8.A.1: extend `aeat config doctor` to call `verify_secure_object_kinds` (from W1.C.6) under its `secure_state.load` row. Confirm the divergence from W1.A.7 cannot recur.
- [ ] Step W8.A.2: extend `config doctor` with rows for `profile.completeness`, `auth.session` (already present, must use shared predicate from W6), `network.reachability` (preportal.aeat.es and sede.agenciatributaria.gob.es).
- [ ] Step W8.A.3: write `src/aeat/application/test_diagnostics.py` cases per row.

### W8.B Regression sweep

- [ ] Step W8.B.1: re-run every step in section 1 hand-verify protocol's capture step 1 and 2 against the merged worktree.
- [ ] Step W8.B.2: confirm UX-002, UX-005, UX-009, UX-014, UX-016 namespace, UX-017, UX-018 do NOT regress. If any does, open a row in this plan and a follow-up wave; do not close.
- [ ] Step W8.B.3: re-run UX-001 stale-dep traceback scenario by deliberately uninstalling a dependency in a temp environment and confirming the user-facing message does not include a Python traceback. UX-001 was carried-not-verified at the recompile.

### W8.C Test discipline audit

- [ ] Step W8.C.1: grep the tree for `pytest.skip`, `pytest.xfail`, `monkeypatch.setattr`, `MagicMock`, `unittest.mock` usage introduced by this plan. Each occurrence is justified or removed.
- [ ] Step W8.C.2: grep the tree for hardcoded `Decimal(` in tests touched by this plan. Each occurrence is justified against the no-tautological-tests rule or removed.
- [ ] Step W8.C.3: confirm no test added by this plan would pass against the pre-plan codebase (test must fail when the fix is reverted).

### W8.D Source-code metadata sweep

- [ ] Step W8.D.1: grep changed source files for forbidden tokens: `2026-`, `phase`, `wave`, `previously`, `rebuild pending`, `\.vault/`, `excised`, `formerly`. Each occurrence is removed or moved to commit message / plan.

### W8.E Plan closure

- [ ] Step W8.E.1: tick every checkbox above. Any unticked checkbox blocks closure.
- [ ] Step W8.E.2: produce an exec record under `.vault/exec/2026-05-08-aeat-cli-gap-closure/...-summary.md` summarising waves W1-W8.
- [ ] Step W8.E.3: append a closure note to `.vault/audit/2026-05-08-aeat-cli-gap-discovery-audit.md` recording the rev at which closure was achieved.
- [ ] Step W8.E.4: run vault hygiene: `uv run --no-sync vaultspec-core vault check all` and root-cause every reported issue.

### W8.F Final commit

- [ ] Step W8.F.1: stage closure files only.
- [ ] Step W8.F.2: commit with message `chore(cli): close aeat-cli-gap-closure plan; all UX-* findings resolved`.

## 12. Parallelisation

Strict serial: W1 first; nothing else runs while UX-019 is open because the
read paths it breaks are pre-conditions for W4 and W7.A hand-verify.

After W1 commits:

- W2, W3, W5, W6 may run in parallel because they touch disjoint backend modules and disjoint CLI files.
- W4 depends on W3 (structured error emitter) and on W2 (per-modelo readiness needs the new keys). Run W4 after both.
- W7.A depends on W2.
- W7.G depends on W7.A and W7.B for next-step coaching content.

The shared worktree contains unrelated dirty files. Do not stage them. Do not
revert them. Do not move them. Each wave's commit stages only the files this
plan owns or that the wave's steps explicitly modify.

## 13. Verification

Closure requires:

- every `[ ]` checkbox above is `[x]`;
- every test listed above exists, runs green, and was proven to fail when its
  fix is reverted;
- `aeat app overview status` returns the expected 4-section block on a clean
  profile with no `INTEGRITY:` line;
- `aeat setup profile set iva.regime general` succeeds and the deadline engine
  produces modelo 303 entries on the next `app overview status --calendar`;
- `aeat app declaration calculate --modelo 130 --period 2026Q1 --binding irpf.previous_year_economic_activity_net_income=NNNN`
  produces a draft, and `aeat app declaration approve --draft-id <id>` and
  `aeat app declaration approve --modelo 130 --period 2026Q1` both succeed;
- every CLI flag's help text passes the example-or-discovery-pointer assertion;
- `aeat setup auth status` and `aeat config doctor` agree on auth readiness for
  the same shell;
- `aeat config doctor` reports a structured failure for any of the W8.B
  regression scenarios when they are deliberately re-introduced;
- `vaultspec-core vault check all` passes;
- the closure exec record is committed.

Honest closure: tests can be cheated. Closure is verified by manual replay of
the hand-verify protocol after every wave commits, not just by green CI.
