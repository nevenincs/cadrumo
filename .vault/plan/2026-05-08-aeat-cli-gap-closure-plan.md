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

- [ ] Step W1.C.1: introduce a typed `SecureObjectDecryptError` exception in `src/aeat/adapters/persistence/storage/errors.py` that carries `namespace`, `row_id`, and the wrapped cause. Distinct from generic `DecryptionError` so consumers can pattern-match.
- [ ] Step W1.C.2: change `secure_objects.list_records` to a fault-isolated iterator. Yield a typed `SecureObjectListItem` Pydantic model with two variants: `SecureObjectListItem.Loaded(record: SecureObjectRecord)` and `SecureObjectListItem.Unreadable(namespace, row_id, reason)`. The decrypt happens row-by-row inside a per-row try/except; failure on row N does not abort row N+1.
- [ ] Step W1.C.3: every `list_records` consumer (`aeat.domain.transactions`, `aeat.domain.invoices`, `aeat.domain.filing.drafts`, `aeat.domain.filing.amendments`, `aeat.domain.usage_ratios`, `aeat.domain.justificante.metadata`, `aeat.domain.submission.records`, `aeat.domain.attachments`, `aeat.application.archive`, `aeat.application.filing.history`, `aeat.application.workflow.runs`) updates its iteration to handle both variants: count `Unreadable` items and propagate the count through the typed application-layer return value (no silent drop).
- [ ] Step W1.C.4: extend the application-layer return types of `_load_transactions`, `_load_invoices`, `_load_drafts` (and equivalents) with an `unreadable_count` field. The CLI renderers consume this field and surface the count.
- [ ] Step W1.C.5: extend the `secure_state.load` diagnostic in `src/aeat/application/diagnostics.py` to actually iterate every populated namespace and report per-namespace `(readable, unreadable)` counts. Today it returns `ok` after a single primary-keyed load; the new check exercises `list_records` for every namespace and surfaces totals.
- [ ] Step W1.C.6: introduce `verify_secure_object_kinds(profile) -> SecureObjectIntegrityReport` in `src/aeat/application/diagnostics.py` that returns the typed per-namespace counts. Both `config doctor` and (optionally) `overview status` warning emission consume it.
- [ ] Step W1.C.7: add an opt-in repair surface `aeat config doctor --quarantine-unreadable` that rewrites unreadable rows into a sibling `secure_objects_quarantine` table and removes them from `secure_objects`. Requires explicit `--yes` confirmation. The user's data (even unreadable ciphertext) is preserved in quarantine; nothing is auto-deleted.
- [ ] Step W1.C.8: confirm no transient metadata (no dates, "phase", vault paths) appears in these edits.

### W1.D CLI surface repair

- [ ] Step W1.D.1: in `src/aeat/entrypoints/cli/_errors.py`, add a typed handler for the secure-objects integrity error that emits a structured CLI error with `Fix:` pointing at `aeat config doctor` and a one-sentence description of what failed. The handler reads the typed exception class; it does not pattern-match on the message string.
- [ ] Step W1.D.2: in `src/aeat/entrypoints/cli/_overview.py`, replace any direct printing of the raw integrity message with a call through the structured-error emitter.
- [ ] Step W1.D.3: in `src/aeat/entrypoints/cli/_declaration.py`, do the same for `declaration review`.
- [ ] Step W1.D.4: confirm no `print(...)` of raw exception messages remains on these read paths.

### W1.E Tests

- [ ] Step W1.E.1: write `tests/live/test_secure_object_read_paths_live.py::test_overview_status_does_not_emit_integrity_error` gated by `@pytest.mark.live` and `AEAT_LIVE_TESTS_ENABLED`. Asserts `aeat app overview status` returns the expected 4-section block; asserts no line containing `INTEGRITY` is present.
- [ ] Step W1.E.2: write `tests/live/test_secure_object_read_paths_live.py::test_overview_calendar_does_not_emit_integrity_error`.
- [ ] Step W1.E.3: write `tests/live/test_secure_object_read_paths_live.py::test_declaration_review_does_not_emit_integrity_error`.
- [ ] Step W1.E.4: write `src/aeat/adapters/persistence/storage/test_secure_object_round_trip.py::test_each_kind_round_trips_across_processes`. Uses a real on-disk store under a temp directory; spawns a child Python process that reads back what the parent process wrote; runs once per registered secure-object kind. No mocks.
- [ ] Step W1.E.5: write `src/aeat/application/test_diagnostics.py::test_secure_state_load_exercises_overview_read_path`. Asserts `verify_secure_object_kinds` triggers the same read code path that `overview status` triggers, by checking call counts on a real backend (no mock).
- [ ] Step W1.E.6: prove each test fails when `git stash` is used on the repair commits and rerun. If a test still passes, it is tautological; rewrite.
- [ ] Step W1.E.7: confirm no test in this wave uses `pytest.skip`, `pytest.xfail`, or `monkeypatch`.

### W1.F Commit checkpoint

- [ ] Step W1.F.1: run `pytest src/aeat/adapters/persistence/storage/ src/aeat/application/test_diagnostics.py` and confirm green.
- [ ] Step W1.F.2: run `pre-commit run --files <changed-files-list>` and confirm green. Root-cause any failure.
- [ ] Step W1.F.3: stage only the files this wave touched: the storage repair, the diagnostics extension, the CLI error handler, the new tests, this plan.
- [ ] Step W1.F.4: commit with message `fix(secure-objects): repair AES-256-GCM tag verification on overview/declaration read paths (UX-019)`.
- [ ] Step W1.F.5: run `git status` to confirm the commit landed and no other files were unintentionally staged.

## 5. W2 - UX-007 profile registry key extension

### W2.A Hand-verify current shape

- [ ] Step W2.A.1: run `aeat setup profile list-keys` and capture the 22 keys returned today.
- [ ] Step W2.A.2: run `aeat setup profile set iva.regime general` and capture the `Clave de perfil desconocida` rejection.
- [ ] Step W2.A.3: read `src/aeat/domain/user_profile/_schema.py` and `src/aeat/domain/user_profile/_values.py`. Record the current key set.
- [ ] Step W2.A.4: read `src/aeat/domain/deadlines/_models.py` and identify which fields the deadline engine consumes from `AutonomoProfile`. Record the engine-required field set.
- [ ] Step W2.A.5: compute the gap: engine-required set minus user-settable set. Confirm the gap matches the audit's `iva.*`, `irpf.*`, `modelos.*` clusters.

### W2.B Schema definition

- [ ] Step W2.B.1: in `src/aeat/domain/user_profile/_schema.py` add field definitions for `iva.regime` with enum values `general | simplificado | recargo-equivalencia | exento | reagp | rebu | not-applicable`.
- [ ] Step W2.B.2: add `iva.sii_enrolled: bool`.
- [ ] Step W2.B.3: add `iva.verifactu: bool`.
- [ ] Step W2.B.4: add `iva.intracomunitario: bool` (ROI registered).
- [ ] Step W2.B.5: add `irpf.regime: enum {directa-normal | directa-simplificada | objetiva | not-applicable}`.
- [ ] Step W2.B.6: add `irpf.activity_type` (CNAE/IAE classification, free-text constrained by registry list).
- [ ] Step W2.B.7: add `modelos.set: list[str]` constrained against the registry's known modelos.
- [ ] Step W2.B.8: add `modelos.cadence: dict[str, enum {monthly | quarterly | annual}]` for per-modelo overrides.
- [ ] Step W2.B.9: confirm every new field is declared as a Pydantic v2 model attribute with strict validation. No `Optional[Any]`, no untyped dict.
- [ ] Step W2.B.10: run `pytest src/aeat/domain/user_profile/test_schema.py` and confirm no regression.

### W2.C Cross-regime validation

- [ ] Step W2.C.1: in `src/aeat/domain/user_profile/_schema.py` (or a new `_cross_regime.py` if it grows large), implement validators that emit warnings (not errors) for incoherent combinations. Examples: `iva.regime = simplificado` with `irpf.regime = directa-normal`; `iva.regime = recargo-equivalencia` with `iva.intracomunitario = true`.
- [ ] Step W2.C.2: implement a hard error for impossible combinations (e.g. `irpf.regime = not-applicable` with `modelos.set` containing `100` and `130`).
- [ ] Step W2.C.3: write `src/aeat/domain/user_profile/test_cross_regime.py` with one test per validator. Each test feeds a specific combination and asserts the warning code or error code returned. Source the truth for each combination from AEAT instructional documentation cited in the test docstring.

### W2.D Round-trip through engine

- [ ] Step W2.D.1: in `src/aeat/application/profile/__init__.py` (or its current API surface), expose a `set_profile_value(key, value)` function that writes through the Pydantic model.
- [ ] Step W2.D.2: confirm that `src/aeat/domain/deadlines` reads the same model on the next run; a value written by `set_profile_value("iva.regime", "general")` is observable to the deadline engine without restart.
- [ ] Step W2.D.3: write `src/aeat/application/profile/test_engine_visibility.py::test_iva_regime_set_visible_to_deadline_engine` proving the round-trip end-to-end.
- [ ] Step W2.D.4: write the same test for `irpf.regime`, `modelos.set`, `iva.sii_enrolled`, `iva.verifactu`, `iva.intracomunitario`.

### W2.E CLI surface

- [ ] Step W2.E.1: in `src/aeat/entrypoints/cli/_setup.py` (or wherever `setup profile list-keys` is registered), confirm the command renders the new keys as soon as the schema exposes them. The CLI must NOT carry its own key list.
- [ ] Step W2.E.2: in the same module, confirm `setup profile set` rejects unknown keys via the schema's `KeyError` translation, not via a hand-coded denylist.
- [ ] Step W2.E.3: ensure the rejection error pipes through the structured emitter from W3 (see W3.B). Until W3 lands, the rejection still uses the existing emitter; do not regress the existing handler.
- [ ] Step W2.E.4: group the output of `setup profile list-keys` by axis: Identity, IVA enrolment, IRPF enrolment, Modelo enrolment. The grouping is a backend property of the schema (axis tag on each field), not CLI-local.

### W2.F Tests

- [ ] Step W2.F.1: write `src/aeat/entrypoints/cli/test_user_cli_surface.py::test_setup_profile_list_keys_includes_iva_regime` asserting the key appears with its data type and valid values.
- [ ] Step W2.F.2: same for `irpf.regime`, `iva.sii_enrolled`, `iva.verifactu`, `iva.intracomunitario`, `modelos.set`, `modelos.cadence`.
- [ ] Step W2.F.3: write `tests/live/test_profile_set_round_trip_live.py::test_set_iva_regime_then_calendar_shows_modelo_303` gated by live env flag. Sets the regime via CLI; runs `app overview status --calendar`; asserts modelo 303 entries are present.
- [ ] Step W2.F.4: write the same live round-trip for IRPF regime impacts (modelo 130 vs modelo 100 calendar).
- [ ] Step W2.F.5: prove each test fails when the schema extensions are reverted.

### W2.G Commit checkpoint

- [ ] Step W2.G.1: run `pytest src/aeat/domain/user_profile/ src/aeat/application/profile/ src/aeat/entrypoints/cli/test_user_cli_surface.py` green.
- [ ] Step W2.G.2: run `pre-commit run --files <changed-files-list>` green.
- [ ] Step W2.G.3: stage only this wave's files plus this plan.
- [ ] Step W2.G.4: commit with message `feat(user-profile): extend schema with IVA, IRPF, modelo enrolment, SII, Verifactu, ROI keys (UX-007)`.

## 6. W3 - UX-012 structured errors and `declaration calculate --binding`

### W3.A Hand-verify

- [ ] Step W3.A.1: run `aeat app declaration calculate --modelo 130 --period 2026Q1` against a profile with no captured prior filing. Capture the binding-missing error line.
- [ ] Step W3.A.2: run `aeat app modelo bindings 130 --period 2026Q1`. Confirm `irpf.previous_year_economic_activity_net_income` appears with source `previous_filing`.
- [ ] Step W3.A.3: identify in `src/aeat/application/filing` (or its current location) the function that loads previous-filing-sourced bindings.
- [ ] Step W3.A.4: identify in `src/aeat/entrypoints/cli/_declaration.py` the function that registers the `calculate` verb. Note the absence of `--binding`.
- [ ] Step W3.A.5: read `src/aeat/entrypoints/cli/_errors.py` and confirm whether a structured-error emitter contract already exists (the prior plan flagged `decorate_typer_app` as not wired at root).

### W3.B Structured error emitter

- [ ] Step W3.B.1: in `src/aeat/core/errors` (or `src/aeat/entrypoints/cli/_errors.py`, depending on current ownership), define a typed `CliErrorRender` value carrying `code`, `headline`, `description`, `did_you_mean`, `fix_command`, `learn_more_topic`, `exit_code`.
- [ ] Step W3.B.2: add a `register_fix_template(code, template)` registry. Templates live as data, not as inline strings in the CLI.
- [ ] Step W3.B.3: register fix templates for `unknown_profile_key` (suggest `setup profile list-keys`), `binding_missing_value` (suggest `app modelo bindings <modelo> --period <P>` and `setup profile set <suggested-key> <value>`), `missing_required_argument` (echo a concrete example), `unknown_option` (suggest `--help`).
- [ ] Step W3.B.4: expose `decorate_typer_app(app)` that installs the structured-error boundary at the root of the Typer app. Wire it from `src/aeat/entrypoints/cli/__init__.py`.
- [ ] Step W3.B.5: write `src/aeat/entrypoints/cli/test_error_registry_contract.py::test_unknown_profile_key_renders_did_you_mean` asserting the rendered output contains the expected `Fix:` line.
- [ ] Step W3.B.6: same for `binding_missing_value` against a real `declaration calculate` invocation (live test).

### W3.C Backend supplier path

- [ ] Step W3.C.1: in `src/aeat/application/filing` add a `BindingSelector` value that distinguishes `from_profile`, `from_previous_filing`, `from_explicit_input`.
- [ ] Step W3.C.2: add `supply_binding(profile, modelo, period, key, value)` that records an `from_explicit_input` value scoped to the next `calculate` invocation.
- [ ] Step W3.C.3: confirm `from_previous_filing` lookup uses the existing `registry capture-filed-data` store. If a captured prior filing is present locally, `calculate` consumes it without explicit input.
- [ ] Step W3.C.4: when `from_previous_filing` lookup fails AND no `from_explicit_input` is supplied, raise a typed `BindingMissingValueError` carrying the binding key and source category.
- [ ] Step W3.C.5: register a fix template against `BindingMissingValueError` that points at `app registry capture-filed-data` and `--binding KEY=VALUE`.
- [ ] Step W3.C.6: confirm `BindingSelector` is a Pydantic v2 model (per project mandate). No untyped dict.

### W3.D CLI wiring

- [ ] Step W3.D.1: add `--binding KEY=VALUE` (repeatable) to the `calculate` verb in `src/aeat/entrypoints/cli/_declaration.py`. The flag parses `KEY=VALUE` strings into a list of `(key, value)` tuples.
- [ ] Step W3.D.2: parse failure (no `=`, empty key, empty value) raises a typed CLI usage error rendered through the structured emitter.
- [ ] Step W3.D.3: each parsed tuple is forwarded to `application.filing.supply_binding` before `calculate` runs.
- [ ] Step W3.D.4: confirm the CLI does NOT validate the value against the registry's expected type; that validation is the backend's responsibility.
- [ ] Step W3.D.5: update help text to reference `app modelo bindings <modelo> --period <P>` for discovery.

### W3.E Tests

- [ ] Step W3.E.1: write `src/aeat/application/filing/test_binding_supplier.py::test_supply_binding_consumed_by_calculate` (no live).
- [ ] Step W3.E.2: write the same for `from_previous_filing` lookup against a captured prior filing.
- [ ] Step W3.E.3: write `tests/live/test_declaration_calculate_binding_live.py::test_calculate_modelo_130_with_explicit_binding`. Hand-verify expected cuota against AEAT pago-fraccionado bracket per RD 439/2007 art. 110 BEFORE encoding.
- [ ] Step W3.E.4: write `src/aeat/entrypoints/cli/test_error_registry_contract.py::test_binding_missing_value_renders_fix_pointers` against the failing path.
- [ ] Step W3.E.5: prove tests fail when the supplier path is reverted.

### W3.F Commit checkpoint

- [ ] Step W3.F.1: run the new tests green.
- [ ] Step W3.F.2: run `pre-commit run` green.
- [ ] Step W3.F.3: commit with message `feat(filing,cli): structured errors and declaration calculate --binding supplier path (UX-012)`.

## 7. W4 - UX-020, UX-021, UX-006 declaration verb consolidation and readiness honesty

### W4.A Hand-verify

- [ ] Step W4.A.1: run `aeat app declaration status --modelo 303 --period 2026Q1` and confirm it resolves a draft.
- [ ] Step W4.A.2: run `aeat app declaration approve --modelo 303 --period 2026Q1` and confirm `No such option: --modelo`.
- [ ] Step W4.A.3: run `aeat app declaration validate --modelo 303 --period 2026Q1` and confirm the same.
- [ ] Step W4.A.4: run `aeat app declaration calculate --modelo 303 --period 2026Q1` and confirm `Bloqueos: N` is reported as a count without enumeration.
- [ ] Step W4.A.5: run `aeat setup status` against a profile with 2/22 keys set and confirm `Perfil listo: si` is emitted.

### W4.B DraftSelector contract

- [ ] Step W4.B.1: in `src/aeat/application/filing` (or `src/aeat/application/review`, whichever owns draft access today) define a `DraftSelector` Pydantic value with two constructors: `from_id(draft_id)` and `from_modelo_period(profile, modelo, period)`.
- [ ] Step W4.B.2: add `resolve_draft(selector) -> Draft` that returns the draft or raises `DraftNotFoundError`.
- [ ] Step W4.B.3: every declaration application API (`status`, `approve`, `validate`, `preview`, `export`, `edit`, `verify`, `review`) accepts a `DraftSelector` rather than per-verb flag tuples.
- [ ] Step W4.B.4: write `src/aeat/application/filing/test_draft_selector.py::test_resolve_by_id`, `test_resolve_by_modelo_period`, `test_unresolvable_raises_typed_error`.

### W4.C Blocker enumeration

- [ ] Step W4.C.1: in the calculate path, identify the function that computes the blocker count today. Promote its return value from a count to a list of `Blocker(code, headline, fix_command)` entries.
- [ ] Step W4.C.2: extend the `CalculateResult` Pydantic model with `blockers: list[Blocker]`.
- [ ] Step W4.C.3: do NOT remove the count; it is computed from the list.

### W4.D Readiness matrix

- [ ] Step W4.D.1: in `src/aeat/application/setup_status.py` add `compute_per_modelo_readiness(profile) -> ReadinessMatrix` returning per-modelo `ready: bool`, `missing_required: list[str]`, `missing_optional: list[str]`.
- [ ] Step W4.D.2: replace the boolean `Perfil listo` field consumed by `setup status` with a derived expression: `ready_overall = all(modelo.ready for modelo in modelos.set)` AND every required key is set. The boolean lives only in the rendered output, not in the application layer.
- [ ] Step W4.D.3: add `--for-modelo` to `setup status` and `setup profile validate` that filters the matrix to one modelo.
- [ ] Step W4.D.4: add `--all-keys` (or `--unset`) to `setup profile show` that emits one row per registered key, with `<unset>` for empty optionals. The list of registered keys comes from the schema; the CLI does not maintain its own list.

### W4.E CLI wiring

- [ ] Step W4.E.1: in `src/aeat/entrypoints/cli/_declaration.py` add `--draft-id` and `(--modelo, --period)` flag pack to every verb. Parsing fails fast if both `--draft-id` and `--modelo`/`--period` are passed; the resulting CLI usage error renders through the structured emitter.
- [ ] Step W4.E.2: each verb constructs a `DraftSelector` and delegates to its application function.
- [ ] Step W4.E.3: in `_declaration.py` calculate path, render the new `blockers` list inline. `Siguiente:` becomes a runnable command (e.g. `aeat app declaration review --modelo 303 --period 2026Q1`) when blockers exist; renders `(none)` when blockers is empty.
- [ ] Step W4.E.4: in `src/aeat/entrypoints/cli/_setup.py` consume `compute_per_modelo_readiness` for `setup status` and `profile validate`; render the matrix when `--for-modelo` is absent.

### W4.F Tests

- [ ] Step W4.F.1: write `src/aeat/entrypoints/cli/test_user_cli_surface.py::test_declaration_verbs_accept_draft_id` parametrised over verbs.
- [ ] Step W4.F.2: write the same for `(--modelo, --period)` selector form.
- [ ] Step W4.F.3: write `test_declaration_verbs_reject_both_selectors_simultaneously` proving the typed usage error.
- [ ] Step W4.F.4: write `tests/live/test_declaration_calculate_blockers_live.py::test_calculate_enumerates_blockers` against a deliberately-blocked draft.
- [ ] Step W4.F.5: write `src/aeat/application/test_setup_status.py::test_per_modelo_readiness_matrix` proving each modelo's readiness against a hand-derived ground truth (which keys are required for which modelo, sourced from registry TOMLs).
- [ ] Step W4.F.6: write `test_perfil_listo_only_true_when_every_modelo_in_set_is_ready` proving the boolean does not oversell.

### W4.G Commit checkpoint

- [ ] Step W4.G.1: run new and adjacent tests green.
- [ ] Step W4.G.2: pre-commit green.
- [ ] Step W4.G.3: commit with message `refactor(declaration,setup): unified DraftSelector, blocker enumeration, per-modelo readiness (UX-006, UX-020, UX-021)`.

## 8. W5 - UX-004 help-text uplift

### W5.A Catalogue

- [ ] Step W5.A.1: enumerate every Click/Typer option declared under `src/aeat/entrypoints/cli/`. Use `grep -rn "option(" src/aeat/entrypoints/cli/` and `grep -rn "Argument(" src/aeat/entrypoints/cli/` (via the project's preferred search tool).
- [ ] Step W5.A.2: for each option, record `module:line`, current help text, and whether help text references a discovery command.
- [ ] Step W5.A.3: classify each option as `OK` (matches `auth providers` quality bar) or `NEEDS_UPLIFT`.

### W5.B Uplift content

- [ ] Step W5.B.1: for every `NEEDS_UPLIFT` row, replace the help string with a one-sentence description, one example, and one discovery pointer where applicable.
- [ ] Step W5.B.2: confirm help strings are sourced from the i18n catalogue (`src/aeat/entrypoints/cli/_i18n.py`) where the project already routes user-facing text through it.
- [ ] Step W5.B.3: confirm no help string references "phase", "wave", dates, or vault paths.

### W5.C Tests

- [ ] Step W5.C.1: write `src/aeat/entrypoints/cli/test_help_text_quality.py::test_every_option_has_example_or_discovery_pointer`. Programmatically inspects every registered option's `help` attribute and asserts it contains either `Ejemplo:` / `Example:` or a discovery-command reference. The list of options is enumerated from the live Typer app, not hardcoded.
- [ ] Step W5.C.2: this test must fail if a future contributor adds a flag without uplift.

### W5.D Commit checkpoint

- [ ] Step W5.D.1: tests green.
- [ ] Step W5.D.2: pre-commit green.
- [ ] Step W5.D.3: commit with message `docs(cli): uplift every flag's help text to discovery-pointer quality bar (UX-004)`.

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
