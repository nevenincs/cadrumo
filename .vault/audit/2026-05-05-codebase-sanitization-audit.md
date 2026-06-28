---
tags:
  - '#audit'
  - '#codebase-sanitization'
date: '2026-05-05'
modified: '2026-05-05'
related: []
---



# `codebase-sanitization` audit: `python sanitization rolling audit`

## Scope

Read-only mechanical audit of all Python files enumerated by `fd -e py | Sort-Object` on 2026-05-05.

Audit surface: 747 Python files.

Rewrite scope: append-only findings rows for suspicious TODO, stub, shadow, shim, obsolete, compatibility, placeholder, or not-implemented language in comments, docstrings, function names, and method names.

Row format: `file:line | marker | short reference`.

## Findings

Rows below are generated from `.tmp/codebase-sanitization-findings.sqlite3`.

```text
file:line | marker | short reference
docs/conf.py:29 | stub | conf-stubs | Source file types — both reStructuredText (autodoc stubs, index) and MyST
docs/conf.py:45 | legacy | conf-legacy | Legacy narrative docs scheduled for removal (heavy dev-process
src/aeat/adapters/inbound/financial/providers/_xlsx.py:72 | placeholder | xlsx-placeholders | Initialise the validation metadata placeholders.
src/aeat/adapters/inbound/justificante/_extract.py:131 | legacy | just-extract-legacy | Legacy 2021 modelos (iText 2.1.4 producer) print value-then-label
src/aeat/adapters/inbound/justificante/_parsers/__init__.py:43 | not-implemented | pymupdf-not-impl | PYMUPDF backend is not implemented yet; use PDFPLUMBER (the default).
src/aeat/adapters/inbound/pdf/_scrub.py:111 | placeholder | placeholder-random | deterministic placeholder
src/aeat/adapters/inbound/pdf/test_scrub.py:29 | placeholder | placeholder-doc | redacted to the synthetic placeholder
src/aeat/adapters/inbound/pdf/test_scrub.py:32 | placeholder | placeholder-doc2 | rewritten to the synthetic 00000000T placeholder
src/aeat/adapters/inbound/pdf/test_scrub.py:104 | placeholder | placeholder-doc3 | canonical synthetic placeholder
src/aeat/adapters/inbound/sanitizer/_metadata.py:5 | legacy | legacy-doc | scrub_docinfo deletes the legacy DocInfo dictionary
src/aeat/adapters/inbound/sanitizer/_pipeline.py:102 | legacy | legacy-flag | deletes the legacy DocInfo
src/aeat/adapters/inbound/sanitizer/_streams.py:269 | legacy | legacy-encoding | PDFDocEncoding for legacy literal strings
src/aeat/adapters/inbound/sanitizer/fixtures.py:8 | hardcoded | harderror-doc | hard error rather than a silent no-op
src/aeat/adapters/inbound/sanitizer/fixtures.py:8 | no-op | no-op-doc | hard error rather than a silent no-op or double-stripped
src/aeat/adapters/inbound/sanitizer/test_adversarial_absence.py:126 | placeholder | placeholder-doc | No fixture carries a placeholder string from a partially-filled mapping
src/aeat/adapters/inbound/sanitizer/test_adversarial_absence.py:128 | scaffold | scaffold-doc | aeat sanitize prepare-map scaffolds entries with placeholder
src/aeat/adapters/inbound/sanitizer/test_adversarial_absence.py:145 | no-op | no-op-doc | No-op test that documents the skip-clean state for CI
src/aeat/adapters/inbound/sanitizer/test_metadata.py:5 | legacy | legacy-doc | Every legacy DocInfo key the sanitiser must wipe
src/aeat/adapters/inbound/sanitizer/test_metadata.py:9 | no-op | no-op-doc | A no-op path when the source PDF carries no DocInfo / XMP at all
src/aeat/adapters/inbound/sanitizer/test_round_trip.py:62 | legacy | legacy-cache | the legacy layout parsed each PDF twice
src/aeat/adapters/outbound/aeat/auth/__init__.py:145 | not-implemented | ni-factory | auth provider is not implemented yet
src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py:111 | not-implemented | ni-doc | NotImplementedError: Always.
src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py:113 | not-implemented | ni-raise | raise NotImplementedError(
src/aeat/adapters/outbound/aeat/auth/_clave_movil.py:19 | placeholder | marker-doc | placeholders and a provider_kind marker for the session detail
src/aeat/adapters/outbound/aeat/auth/_clave_movil.py:310 | legacy | legacy-login | If neither is available (legacy
src/aeat/adapters/outbound/aeat/auth/test_authenticator.py:3 | fake | no-fake-policy | Zero mocks / patches / fakes (global ban)
src/aeat/adapters/outbound/aeat/auth/test_authenticator_live.py:10 | fake | no-fake-policy | zero mocks, patches, fakes, or monkey-patched
src/aeat/adapters/outbound/aeat/auth/test_certificate.py:4 | fake | no-fake-policy | no mocks, no fakes, no checked-in fixtures
src/aeat/adapters/outbound/aeat/auth/test_certificate.py:291 | legacy | legacy-testnet | legacy TEST-NET-1 address (192.0.2.1)
src/aeat/adapters/outbound/aeat/auth/test_certificate.py:389 | not-implemented | ni-test | HTTPX_FALLBACK has no browser path
src/aeat/adapters/outbound/aeat/auth/test_certificate.py:407 | placeholder | placeholder-path | placeholder_p12 = tmp_path / "op.p12"
src/aeat/adapters/outbound/aeat/auth/test_certificate.py:408 | placeholder | placeholder-bytes | placeholder_p12.write_bytes(b"placeholder")
src/aeat/adapters/outbound/aeat/auth/test_certificate.py:409 | placeholder | placeholder-env | setenv AEAT_CERTIFICATE_PATH to placeholder_p12
src/aeat/adapters/outbound/aeat/auth/test_certificate.py:416 | placeholder | placeholder-assert | settings.aeat_certificate_path == placeholder_p12
src/aeat/adapters/outbound/aeat/auth/test_gate.py:84 | placeholder | placeholder-env | PYTEST_CURRENT_TEST set to placeholder
src/aeat/adapters/outbound/aeat/auth/test_health.py:4 | fake | no-fake-policy | no mocks, no fakes, no checked-in fixtures
src/aeat/adapters/outbound/aeat/browser/test_session.py:24 | dummy | dummy-test-double | class DummyEvasion(EvasionStrategy)
src/aeat/adapters/outbound/aeat/sede/_declarations.py:416 | No-op | no-op-return-doc | No-op return on success.
src/aeat/adapters/outbound/aeat/sede/_notifications.py:73 | placeholder | placeholder-state | The `pendiente` value marks the placeholder state
src/aeat/adapters/outbound/aeat/sede/test_parse.py:5 | placeholder | redacted-placeholder | redacted to synthetic but schema-valid placeholders
src/aeat/adapters/outbound/google/test_auth_helpers.py:5 | fakes | testing-guidelines | Project rules forbid mocks, fakes, stubs, and patches
src/aeat/adapters/outbound/google/test_auth_helpers.py:37 | placeholder | hardcoded-placeholder | _OAUTH_CLIENT_SECRET = "client-secret"
src/aeat/adapters/outbound/google/test_google.py:5 | fakes | testing-guidelines | Project rules forbid mocks, fakes, stubs, and patches
src/aeat/adapters/outbound/google/test_google.py:39 | placeholder | hardcoded-placeholder | _OAUTH_CLIENT_SECRET = "client-secret"
src/aeat/adapters/outbound/llm/_models.py:165 | placeholder | prompt-seed | description="Placeholder seed for casilla extraction workflows."
src/aeat/adapters/outbound/llm/_models.py:174 | placeholder | prompt-seed | description="Placeholder seed for manual rule extraction workflows."
src/aeat/adapters/outbound/llm/_prompts.py:22 | placeholder | template-placeholder | Substitutes `{...}` placeholders in PromptDefinition.template
src/aeat/adapters/outbound/llm/_test_redaction.py:105 | no-op | redaction-idempotent | re-applying the redaction rules to a redacted string is a no-op
src/aeat/adapters/persistence/storage/_rotation.py:245 | no-op | idempotent-rotation | Rotating to an identical key is permitted (no-op rotation)
src/aeat/adapters/persistence/storage/_test_rotation.py:9 | no-op | rotation-idempotent-test | is a no-op (every file lands in `skipped`)
src/aeat/adapters/persistence/storage/_test_rotation.py:673 | context-lock-pass | lock-exception-assert | with (pytest.raises(LockAcquisitionError), exclusive_file_lock(rotation_lock_target, timeout=0.0):
src/aeat/adapters/persistence/storage/_test_rotation.py:700 | context-lock-pass | lock-exception-assert | with exclusive_file_lock(rotation_lock_target): pass
src/aeat/adapters/persistence/storage/blob_store/_blob_store.py:415 | noop-pass | rotate-manifest-skip | except (DecryptionError, EncryptionError): pass
src/aeat/adapters/persistence/storage/envelope/_envelope.py:7 | legacy | legacy-payloads | the on-disk schema version (so per-domain migrators can roll forward legacy payloads
src/aeat/adapters/persistence/storage/envelope/_envelope.py:18 | not implemented | migrator-extension-point | Per-domain migrators are not implemented at the substrate level
src/aeat/adapters/persistence/storage/envelope/_envelope.py:118 | placeholder | placeholder-consumer-value | payload is then a placeholder consumer-typed value
src/aeat/adapters/persistence/storage/envelope/_envelope.py:528 | noop-pass | ciphertext-check-pass | except (ValidationError, ValueError): pass
src/aeat/adapters/persistence/storage/errors.py:67 | no-op | error-null-keyring | backend is the no-op `null` keyring
src/aeat/adapters/persistence/storage/errors.py:162 | legacy | compat-error-paths | legacy call-sites that catch `ValueError` from the path helpers in
src/aeat/adapters/persistence/storage/master_key/_master_key.py:268 | no-op | probe-noop-backends | keyring backend is inspected; the no-op `fail.Keyring` and `null.Keyring`
src/aeat/adapters/persistence/storage/master_key/_master_key.py:299 | placeholder | placeholder-keyring-backends | Refuse no-op keyring backends up-front.
src/aeat/adapters/persistence/storage/master_key/_master_key.py:302 | placeholder | placeholder-keyring-backends | are placeholder backends installed when the platform has no usable keychain
src/aeat/adapters/persistence/storage/master_key/_master_key.py:319 | no-op | fail-keyring-detected | OS keychain backend is the no-op fail.Keyring
src/aeat/adapters/persistence/storage/master_key/_master_key.py:326 | no-op | null-keyring-detected | OS keychain backend is the no-op null.Keyring
src/aeat/adapters/persistence/storage/master_key/_master_key.py:346 | no-op | probe-excluded-backend | probe at line above already excluded the no-op
src/aeat/adapters/persistence/storage/master_key/_master_key.py:578 | no-op | chmod-platform-behavior | On Windows os.chmod is a no-op; POSIX gets 0o700
src/aeat/adapters/persistence/storage/master_key/_master_key.py:683 | no-op | chmod-docs | Chmod `target` to 0o700 on POSIX; no-op on Windows
src/aeat/adapters/persistence/storage/master_key/_master_key.py:820 | placeholder | tax-id-placeholder-list | all-zero NIF body — documented placeholder
src/aeat/adapters/persistence/storage/master_key/_master_key.py:842 | placeholder | synthetic-placeholder-sentinel | invalid inputs and for synthetic placeholders alike
src/aeat/adapters/persistence/storage/master_key/_master_key.py:884 | placeholder | real-taxid-placeholder | or use a synthetic placeholder (e.g. '00000000T')
src/aeat/adapters/persistence/storage/master_key/_master_key.py:951 | no-op | backend-unusable | backend itself is unusable (no-op fail/null backend
src/aeat/adapters/persistence/storage/master_key/_test_master_key.py:120 | legacy | legacy-error-hierarchy | inherit from MasterKeyUnavailableError so legacy catchers
src/aeat/adapters/persistence/storage/master_key/_test_master_key.py:521 | no-op | keyring-fallback-tests | no-op fail.Keyring backend
src/aeat/adapters/persistence/storage/master_key/_test_master_key.py:532 | no-op | keyring-absent-fallback | package missing, `fail.Keyring` no-op installed
src/aeat/adapters/persistence/storage/master_key/_test_master_key.py:540 | no-op | failback-noop-keyring | simulated no-op fail.Keyring backend
src/aeat/adapters/persistence/storage/secret_store/_secret_store.py:130 | compatibility | compat-marker | schema_version: Forward-compatibility marker for the index file.
src/aeat/adapters/persistence/storage/sql/_orm.py:15 | TODO | inline-todo | column carries an inline `TODO` marker.
src/aeat/adapters/persistence/storage/sql/_orm.py:56 | TODO | pending-migrate | TODO: migrate to a str-backed JSON column.
src/aeat/adapters/persistence/storage/sql/_orm.py:87 | TODO | pending-migrate | TODO: migrate to a str-backed JSON column.
src/aeat/adapters/persistence/storage/sql/engine.py:38 | no-op | sqlite-noop | No-op for non-SQLite URLs and in-memory databases.
src/aeat/adapters/persistence/storage/sql/engine.py:68 | no-op | sqlite-noop | No-op for non-SQLite URLs and `:memory:`.
src/aeat/adapters/persistence/storage/sql/engine.py:82 | no-op | sqlite-noop | no-op for non-SQLite dialects.
src/aeat/application/auth/_catalogue.py:86 | legacy | legacy-alias | Supports both hyphens (canonical) and underscores (legacy alias).
src/aeat/application/filing/_import.py:5 | scaffold | draft-scaffold | materialises an empty draft scaffold (every casilla `EMPTY`)
src/aeat/application/filing/_import.py:67 | scaffold | draft-scaffold | draft: The freshly built scaffold with every casilla empty.
src/aeat/application/profile/__init__.py:5 | hardcoded | hardcoded_keys | its own hardcoded list of mandatory keys
src/aeat/application/review/_adapters.py:384 | placeholder | placeholder_fn | def _to_placeholder_item(*, draft: FilingDraft, path_str: str) -> FindingReviewItem:
src/aeat/application/review/_models.py:100 | placeholder | placeholder_row | `source` is `None` for the placeholder row emitted when a draft
src/aeat/application/review/test_adapters.py:363 | placeholder | placeholder_status | def test_drafts_pending_emits_placeholder_for_draft_status(tmp_path: Path) -> None:
src/aeat/application/review/test_adapters.py:364 | placeholder | placeholder_status | status=DRAFT with no findings must emit the same placeholder as VALIDATED
src/aeat/application/review/test_adapters.py:375 | placeholder | placeholder_status_pending | def test_drafts_pending_emits_placeholder_when_no_findings_but_status_pending(tmp_path: Path) -> None:
src/aeat/application/review/test_models.py:173 | placeholder | placeholder_row | def test_finding_review_item_allows_none_source_for_placeholder_row()
src/aeat/application/setup/_env_writer.py:204 | compatibility | incompatible_real_tax | Real tax data is incompatible with a published deterministic master key
src/aeat/application/setup/_prompter.py:33 | noop | silent_noop | value has the wrong type. `announce` is a silent no-op by default
src/aeat/application/setup/test_wizard.py:123 | noop | noop_runner | class NoopRunner:
src/aeat/application/transactions/_diagnostics.py:112 | stub | diagnostic_factory_stub | factory the CLI tests can stub
src/aeat/application/workflow/_engine.py:221 | placeholder | placeholder_runid | the `-` placeholders are expected and match the placeholders in the final result
src/aeat/application/workflow/_protocols.py:11 | fakes/stubs | protocol-testing-11 | project forbids mocks/patches/fakes/stubs in its test suite
src/aeat/application/workflow/test_engine.py:624 | placeholder | workflow-placeholder-hash | not the placeholder hash.
src/aeat/core/access_gate/__init__.py:17 | no-op | access-no-op-17 | cannot swap the gate for a no-op because there is no seam to swap
src/aeat/core/access_gate/__init__.py:112 | no-op | access-no-op-112 | typed, auditable refusal rather than a silent no-op.
src/aeat/core/config.py:708 | legacy | config-legacy-backend | Accept legacy adapter enum names while storing settings-shape values.
src/aeat/core/config.py:718 | placeholder | config-placeholder-expediente | Reject templates that omit the {expediente_id} placeholder.
src/aeat/core/config.py:762 | placeholder | config-placeholder-target | Reject templates that omit the {target} placeholder.
src/aeat/core/env_io.py:73 | no-op | envio-noop-73 | local so the finally cleanup is a no-op.
src/aeat/core/errors/_registry.py:234 | placeholder | errors-placeholder-exit | Return the placeholder process exit code for category.
src/aeat/core/json_contract.py:82 | compatibility | json-compat-incompat-82 | schema_version ... bumped only on backwards-incompatible changes.
src/aeat/core/logging.py:67 | placeholder | logging-placeholder-re1 | _PERCENT_PLACEHOLDER_VALUE_RE = re.compile(...)
src/aeat/core/logging.py:68 | placeholder | logging-placeholder-re2 | _PERCENT_PLACEHOLDER_RE = re.compile(...placeholder%...)
src/aeat/core/logging.py:105 | placeholder | logging-placeholder-value | fullmatch(...) on percent placeholder value
src/aeat/core/logging.py:136 | placeholder | logging-placeholders-list | placeholders = list(_PERCENT_PLACEHOLDER_RE.finditer(message))
src/aeat/core/logging.py:138 | placeholder | logging-placeholders-key | keyed scrub of placeholder positional arguments
src/aeat/core/observability/_context.py:275 | legacy | context-legacy-275 | legacy '1' sentinel from earlier code is ignored
src/aeat/core/observability/_models.py:376 | legacy | models-legacy-trace-exit | before exit (legacy traces only).
src/aeat/core/observability/_models.py:394 | compatibility | models-compat-394 | compatible with traces produced before the field was added.
src/aeat/core/observability/_replay.py:8 | obsolete | replay-obsolete-8 | so old traces cannot reintroduce an obsolete CLI shape
src/aeat/core/observability/_replay.py:28 | legacy | replay-legacy-28 | Legacy flags removed from the workflow CLI surface.
src/aeat/core/observability/_replay.py:141 | obsolete | replay-obsolete-141 | refusing to replay run... used removed flag ... obsolete write-era CLI arguments.
src/aeat/core/observability/test_replay.py:102 | legacy | legacy trace fixture | legacy_trace = RunTrace(
src/aeat/core/observability/test_replay.py:116 | legacy | legacy trace persistence | save_trace(legacy_trace)
src/aeat/core/observability/test_replay.py:118 | legacy | legacy trace retrieval | replay_run(legacy_trace.run_id)
src/aeat/core/observability/test_replay.py:170 | legacy | legacy sentinel docstring | Legacy sentinel ``"1"`` must not pollute the trace.
src/aeat/core/observability/test_replay.py:271 | dummy | dummy filename | (vault_dir / "dummy.md").write_text("content", encoding="utf-8")
src/aeat/core/test_logging.py:27 | temporary | test_logging temporary-docstring | Attach a temporary stream handler to the root logger.
src/aeat/core/test_logging.py:104 | placeholder | test_logging placeholder helper | def test_secret_scrubbing_maps_key_hints_to_the_correct_placeholder() -> None:
src/aeat/core/test_logging.py:105 | placeholder | placeholder docstring | Only the placeholder paired with the sensitive key should be scrubbed.
src/aeat/core/test_logging.py:132 | placeholder | placeholder in docstring | Colon-delimited sensitive placeholders should still be scrubbed.
src/aeat/core/test_logging.py:181 | placeholder | placeholder in docstring | List-based log args should preserve placeholder-aware scrubbing.
src/aeat/domain/attachments/_repository.py:172 | no-op | no-op rename comment | final rename, the rename is retried as a no-op and the tempfile is
src/aeat/domain/attachments/_repository.py:191 | temporary | temporary file usage | with tempfile.NamedTemporaryFile(
src/aeat/domain/attachments/_repository.py:442 | temporary | temporary file usage | with tempfile.NamedTemporaryFile(
src/aeat/domain/calculations/registry/_workbook_parity.py:16 | temporary | temporary directory import | from tempfile import TemporaryDirectory
src/aeat/domain/calculations/registry/_workbook_parity.py:427 | temporary | temporary directory usage | with TemporaryDirectory(prefix="aeat-workbook-") as tmp:
src/aeat/domain/calculations/registry/_workbook_parity.py:502 | temporary | temporary directory usage | with TemporaryDirectory(prefix="aeat-xls-conversion-") as tmp:
src/aeat/domain/justificante/_schema.py:49 | legacy | receipt-schema-legacy-doc | present. `None` for legacy receipts that omit the label.
src/aeat/domain/manuals/_loader.py:7 | temporary | loader docstring | Tests exercise it against hand-crafted temporary-directory fixtures.
src/aeat/domain/manuals/_verify.py:137 | placeholder | docstring marker | (sentinel-based reviewer placeholders).
src/aeat/domain/manuals/_verify.py:153 | no-op | inline comment | Explicit no-op for v1; kept to lock the CLI surface.
src/aeat/domain/normatives/test_verify.py:7 | no-op | module docstring | no-op on clean ones.
src/aeat/domain/normatives/test_verify.py:47 | noop | test method name | def test_raise_on_errors_noop_when_clean(self) -> None:
src/aeat/domain/transactions/_models.py:182 | placeholder | txn-models-provenance-placeholder | # Placeholder for a future typed `DecisionProvenance` pydantic record.
src/aeat/domain/usage_ratios/_model.py:119 | no-op | usage-ratios-model-without-ratio-no-op | A no-op when `category` has no current override.
src/aeat/domain/usage_ratios/test_model.py:97 | no-op | usage-ratios-test-without-ratio-noop | Removing an unset category is a no-op.
src/aeat/entrypoints/cli/_test_doctor.py:46 | placeholder | test_oauth_client_secret_placeholder | _OAUTH_CLIENT_SECRET = "client-secret" # noqa: S105 - test-only placeholder
src/aeat/entrypoints/cli/_test_doctor.py:479 | placeholder | master_key_file_placeholder_bytes | (secret_dir / name).write_bytes(b"placeholder")
src/aeat/entrypoints/cli/_test_doctor.py:494 | placeholder | master_kdf_file_placeholder_bytes | (secret_dir / "master.kdf").write_bytes(b"placeholder")
src/aeat/entrypoints/cli/auth/_registry.py:147 | NotImplementedError | provider_not_implemented_bridge | except NotImplementedError as exc:
src/aeat/entrypoints/cli/auth/_render.py:55 | legacy | health_summary_legacy_token | cert-provider`s legacy sentinel token
src/aeat/entrypoints/cli/auth/_render.py:165 | no-op | status_noop_no_session_line | Render the friendly no-op line used by status/logout when no session exists.
src/aeat/entrypoints/cli/auth/test_auth_cli.py:345 | noop | logout_noop_sessionless | def test_logout_without_session_is_noop(self, isolated_token_dir: Path) -> None:
src/aeat/entrypoints/cli/filing/__init__.py:596 | scaffold | scaffold translation key | cli.filing.import.scaffold_created
src/aeat/entrypoints/cli/financial/ingest.py:117 | legacy | legacy persist toggle doc | legacy stdout-only pipe workflow keeps working
src/aeat/entrypoints/cli/financial/test_cli.py:160 | legacy | legacy behavior doc | legacy stdout-only pipe behaviour
src/aeat/entrypoints/cli/financial/test_profile.py:280 | placeholder | placeholder test name | as_placeholder
src/aeat/locales/manager.py:23 | scaffold | scaffolding docs | scaffolding, and structural health
src/aeat/locales/manager.py:94 | scaffold | scaffold method | def scaffold(self) -> None
tests/_marker_hook.py:27 | noop | no-op collection comment | no-op because their marker sets are identical
tests/_marker_hook.py:70 | compat | older pytest compatibility | older pytest compatibility
tests/fixtures/pdf_corpus/__init__.py:1 | scaffold | fixture scaffolding docs | PDF corpus fixture scaffolding
tests/import_contract/adapters/inbound/justificante/test_parser.py:246 | dummy | dummy fixture filename | pdf = tmp_path / "dummy.pdf"
tests/import_contract/domain/transactions/test_catalogue.py:441 | no-op | test_set_classification_normalises_classified_by_whitespace_for_idempotence | every no-op re-classify would append to history
tests/test_config.py:140 | placeholder | test_rejects_template_without_placeholder | /x/no-placeholder/y
```

## Context Cross-References

Rows below are generated from `.tmp/codebase-sanitization-findings.sqlite3` context records.

```text
file:line | marker | feature | confidence | vault refs | possible cause/context
docs/conf.py:29 | stub | docs | medium | .vault\\adr\\2026-04-12-docs-rewrite-adr.md | Marker refers to docs rewrite cleanup and autodoc/MyST source style
docs/conf.py:45 | legacy | docs | medium | .vault\\adr\\2026-04-12-docs-rewrite-adr.md | Legacy docs narrative is being removed/rewrite scoped for documentation pipeline
src/aeat/adapters/inbound/financial/providers/_xlsx.py:72 | placeholder | financial | medium | .vault\\adr\\2026-04-30-aeat-restructure-adr.md | Financial provider package maps to the ingest pipeline and value validation metadata path
src/aeat/adapters/inbound/justificante/_extract.py:131 | legacy | justificante | high | .vault\\adr\\2026-04-12-justificante-parser-adr.md | Legacy 2021 justificante print layout behavior is documented during parser migration
src/aeat/adapters/inbound/justificante/_parsers/__init__.py:43 | not-implemented | justificante | high | .vault\\adr\\2026-04-12-justificante-parser-adr.md | Parser backend choice prefers pdfplumber and documents pymupdf as not yet supported
src/aeat/adapters/inbound/pdf/_scrub.py:111 | placeholder | pdf-sanitizer | medium | .vault\\adr\\2026-04-25-pdf-sanitizer-adr.md | Scrubber uses deterministic placeholder substitution behavior in PDF sanitization
src/aeat/adapters/inbound/pdf/test_scrub.py:29 | placeholder | pdf-sanitizer | medium | .vault\\adr\\2026-04-25-pdf-sanitizer-adr.md | Sanitization tests assert synthetic placeholder replacement behavior for redacted output
src/aeat/adapters/inbound/pdf/test_scrub.py:32 | placeholder | pdf-sanitizer | medium | .vault\\adr\\2026-04-25-pdf-sanitizer-adr.md | Sanitization tests cover synthetic 00000000T placeholder handling in fixtures
src/aeat/adapters/inbound/pdf/test_scrub.py:104 | placeholder | pdf-sanitizer | medium | .vault\\adr\\2026-04-25-pdf-sanitizer-adr.md | Canonical synthetic placeholder behavior is part of sanitizer fixture strategy
src/aeat/adapters/inbound/sanitizer/_metadata.py:5 | legacy | pdf-sanitizer | high | .vault\\adr\\2026-04-25-pdf-sanitizer-adr.md | DocInfo and XMP scrubbing are explicit sanitizer contract requirements
src/aeat/adapters/inbound/sanitizer/_pipeline.py:102 | legacy | pdf-sanitizer | high | .vault\\adr\\2026-04-25-pdf-sanitizer-adr.md | Pipeline legacy metadata removal aligns with sanitizer metadata-stripping contract
src/aeat/adapters/inbound/sanitizer/_streams.py:269 | legacy | pdf-sanitizer | high | .vault\\adr\\2026-04-25-pdf-sanitizer-adr.md | Legacy PDFDocEncoding literal handling is part of sanitizer compatibility rules
src/aeat/adapters/inbound/sanitizer/fixtures.py:8 | hardcoded | pdf-sanitizer | medium | .vault\\adr\\2026-04-25-pdf-sanitizer-adr.md | Fixture handling should fail hard instead of silently no-opping malformed fixtures
src/aeat/adapters/inbound/sanitizer/fixtures.py:8 | no-op | pdf-sanitizer | medium | .vault\\adr\\2026-04-25-pdf-sanitizer-adr.md | No-op edge behavior in fixture pipeline is part of sanitizer contract checks
src/aeat/adapters/inbound/sanitizer/test_adversarial_absence.py:126 | placeholder | pdf-sanitizer | low | .vault\\audit\\2026-05-05-codebase-sanitization-audit.md | This test validates no placeholder leakage in sanitizer mapping inputs
src/aeat/adapters/inbound/sanitizer/test_adversarial_absence.py:128 | scaffold | pdf-sanitizer | low | .vault\\audit\\2026-05-05-codebase-sanitization-audit.md | This behavior is described in sanitizer adversarial mapping tests for prepared placeholders
src/aeat/adapters/inbound/sanitizer/test_adversarial_absence.py:145 | no-op | pdf-sanitizer | low | .vault\\audit\\2026-05-05-codebase-sanitization-audit.md | No-op CI skip-clean behavior is intentional in sanitizer tests
src/aeat/adapters/inbound/sanitizer/test_metadata.py:5 | legacy | pdf-sanitizer | high | .vault\\adr\\2026-04-25-pdf-sanitizer-adr.md | Sanitizer contract explicitly requires deleting all legacy DocInfo keys
src/aeat/adapters/inbound/sanitizer/test_metadata.py:9 | no-op | pdf-sanitizer | high | .vault\\adr\\2026-04-25-pdf-sanitizer-adr.md | Sanitizer contract documents no-op path when DocInfo/XMP metadata is absent
src/aeat/adapters/inbound/sanitizer/test_round_trip.py:62 | legacy | pdf-sanitizer | medium | .vault\\adr\\2026-04-25-pdf-sanitizer-adr.md | Legacy round-trip parsing behavior is captured by sanitizer test expectations
src/aeat/adapters/outbound/aeat/auth/__init__.py:145 | not-implemented | auth | medium | .vault\\adr\\2026-04-12-cert-auth-adr.md | Auth provider factory includes non-implemented provider branch and shape by design
src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py:111 | not-implemented | auth | high | .vault\\adr\\2026-04-12-cert-auth-adr.md | HTTPX fallback backend is documented and limited to verify-only path
src/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py:113 | not-implemented | auth | high | .vault\\adr\\2026-04-12-cert-auth-adr.md | Fallback path raises NotImplementedError for browser actions by design
src/aeat/adapters/outbound/aeat/auth/_clave_movil.py:19 | placeholder | auth | low | .vault\\research\\2026-05-04-live-filing-data-capture-research.md | Clave-movil session model carries provider kind marker fields and placeholder state
src/aeat/adapters/outbound/aeat/auth/_clave_movil.py:310 | legacy | auth | low | .vault\\reference\\2026-04-24-aeat-verify-reference.md | Legacy Clave-movil fallback constraints are captured in auth/provider reference behavior
src/aeat/adapters/outbound/aeat/auth/test_authenticator.py:3 | fake | testing-guidelines | high | .vault\\adr\\2026-04-17-pytest-only-testing-adr.md | Auth tests are expected to follow no-mocks/no-fakes policy
src/aeat/adapters/outbound/aeat/auth/test_authenticator_live.py:10 | fake | testing-guidelines | high | .vault\\adr\\2026-04-17-pytest-only-testing-adr.md | Live and auth test constraints emphasize no mocks, no fakes, and no monkey patching
src/aeat/adapters/outbound/aeat/auth/test_certificate.py:4 | fake | aeat-auth-test-policy | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Sanitization test fixture intentionally uses declared no-fake rule for AEAT auth tests
src/aeat/adapters/outbound/aeat/auth/test_certificate.py:291 | legacy | aeat-auth-certificate-test | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Test fixture uses TEST-NET-1 legacy address for deterministic auth integration simulation
src/aeat/adapters/outbound/aeat/auth/test_certificate.py:389 | not-implemented | aeat-auth-certificate-test | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Fallback path is intentionally unimplemented for browser-dependent certificate flow test coverage
src/aeat/adapters/outbound/aeat/auth/test_certificate.py:407 | placeholder | aeat-auth-certificate-test | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Test creates temporary placeholder certificate path file for safe placeholder credential flow
src/aeat/adapters/outbound/aeat/auth/test_certificate.py:408 | placeholder | aeat-auth-certificate-test | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Test seeds placeholder certificate bytes to exercise file-based certificate loading path
src/aeat/adapters/outbound/aeat/auth/test_certificate.py:409 | placeholder | aeat-auth-certificate-test | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Certificate path is injected via env var to validate settings mapping with placeholder artifact
src/aeat/adapters/outbound/aeat/auth/test_certificate.py:416 | placeholder | aeat-auth-certificate-test | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Assertion verifies placeholder certificate path is correctly propagated into settings
src/aeat/adapters/outbound/aeat/auth/test_gate.py:84 | placeholder | aeat-auth-gate-test | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Test sets current test marker placeholder env var for gate flow isolation context
src/aeat/adapters/outbound/aeat/auth/test_health.py:4 | fake | aeat-auth-health-test | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Health tests declare no-fake policy as part of sanitization constraints
src/aeat/adapters/outbound/aeat/browser/test_session.py:24 | dummy | aeat-browser-session-test | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Browser session test uses a dummy strategy object to isolate evasion behavior
src/aeat/adapters/outbound/aeat/sede/_declarations.py:416 | No-op | aeat-sede-declarations | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Declaration operation returns early on success, documented as no-op success path
src/aeat/adapters/outbound/aeat/sede/_notifications.py:73 | placeholder | aeat-sede-notifications | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Notification state value is intentionally a placeholder marker for pending processing
src/aeat/adapters/outbound/aeat/sede/test_parse.py:5 | placeholder | aeat-sede-parse | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Test fixtures use synthetic placeholders to remain schema-valid while avoiding real data
src/aeat/adapters/outbound/google/test_auth_helpers.py:5 | fakes | google-auth-test-policy | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Google auth tests document no-mock/fake/patch policy for integration-style verification
src/aeat/adapters/outbound/google/test_auth_helpers.py:37 | placeholder | google-auth-test | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Test helper hardcodes placeholder OAuth client secret for local test determinism
src/aeat/adapters/outbound/google/test_google.py:5 | fakes | google-auth-test-policy | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Google auth suite reiterates test guideline: no mocks, fakes, stubs, or patches
src/aeat/adapters/outbound/google/test_google.py:39 | placeholder | google-auth-test | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Test hardcodes placeholder OAuth client secret per documented test fixture policy
src/aeat/adapters/outbound/llm/_models.py:165 | placeholder | llm-prompt-models | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Model prompt seeds intentionally use placeholder text for extraction workflow seeding
src/aeat/adapters/outbound/llm/_models.py:174 | placeholder | llm-prompt-models | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Model prompt seed values use placeholders for manual rule extraction workflow examples
src/aeat/adapters/outbound/llm/_prompts.py:22 | placeholder | llm-prompts | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Prompt template engine performs placeholder substitution in template strings
src/aeat/adapters/outbound/llm/_test_redaction.py:105 | no-op | llm-redaction | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Redaction is idempotent; rerunning on redacted text should yield unchanged output
src/aeat/adapters/persistence/storage/_rotation.py:245 | no-op | storage-key-rotation | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Rotation routine can no-op when the same key is provided by design
src/aeat/adapters/persistence/storage/_test_rotation.py:9 | no-op | storage-key-rotation-tests | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Rotation test documents no-op behavior when all payloads already map to skipped path
src/aeat/adapters/persistence/storage/_test_rotation.py:673 | context-lock-pass | storage-key-rotation-tests | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Exception-path coverage for lock acquisition is validated to protect concurrent rotation behavior
src/aeat/adapters/persistence/storage/_test_rotation.py:700 | context-lock-pass | storage-key-rotation-tests | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Context manager pass block confirms lock-protected critical section entry/exit succeeds
src/aeat/adapters/persistence/storage/blob_store/_blob_store.py:415 | noop-pass | blob-store | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Rotate-manifest flow intentionally swallows decryption/encryption exceptions to allow manifest fallback
src/aeat/adapters/persistence/storage/envelope/_envelope.py:7 | legacy | storage-envelope | high | .vault\audit\2026-05-05-codebase-sanitization-audit.md | Legacy schema migration path intentionally preserved for on-disk payload roll-forward
src/aeat/adapters/persistence/storage/envelope/_envelope.py:18 | not implemented | secure-persistence-foundation | medium | .vault\adr\2026-04-27-secure-persistence-foundation-adr.md | Per-domain migrators are defined in the secure persistence design but are only required from Wave 3, so Wave 1 behavior is a placeholder no-op contract.
src/aeat/adapters/persistence/storage/envelope/_envelope.py:118 | placeholder | secure-persistence-foundation | low | .vault\adr\2026-04-27-secure-persistence-foundation-adr.md | Secure persistence envelope loading is typed by payload model and includes compatibility handling for placeholder consumer typed values.
src/aeat/adapters/persistence/storage/envelope/_envelope.py:528 | noop-pass | secure-persistence-foundation | low | .vault\adr\2026-04-27-secure-persistence-foundation-adr.md | Envelope load path may swallow decryption/validation errors while preserving compatibility after cipher text checks.
src/aeat/adapters/persistence/storage/errors.py:67 | no-op | secure-persistence-foundation | medium | .vault\adr\2026-04-27-secure-persistence-foundation-adr.md | Master-key backend architecture documents optional keyring integration and fallback/no-op handling for unusable providers.
src/aeat/adapters/persistence/storage/errors.py:162 | legacy | (none) | low | (none) | No meaningful vault context was found; marker appears local to path-helper legacy compatibility branches.
src/aeat/adapters/persistence/storage/master_key/_master_key.py:268 | no-op | secure-persistence-foundation | medium | .vault\adr\2026-04-30-secure-persistence-foundation-wave17-adr.md | Placeholder backend handling is part of key management behavior documented for hardened master-key providers.
src/aeat/adapters/persistence/storage/master_key/_master_key.py:299 | placeholder | secure-persistence-foundation | medium | .vault\adr\2026-04-30-secure-persistence-foundation-wave17-adr.md | Secure profile handling marks no-op keyring placeholders as not suitable backends.
src/aeat/adapters/persistence/storage/master_key/_master_key.py:302 | placeholder | secure-persistence-foundation | medium | .vault\adr\2026-04-30-secure-persistence-foundation-wave17-adr.md | Placeholder keyring backends are treated as unusable and must be rejected before use.
src/aeat/adapters/persistence/storage/master_key/_master_key.py:319 | no-op | secure-persistence-foundation | low | .vault\adr\2026-04-27-secure-persistence-foundation-adr.md | Fail.Keyring provider is excluded as part of secure keyring backend probing behavior.
src/aeat/adapters/persistence/storage/master_key/_master_key.py:326 | no-op | secure-persistence-foundation | low | .vault\adr\2026-04-27-secure-persistence-foundation-adr.md | Null keyring placeholder is treated as an unusable backend in secure master-key discovery.
src/aeat/adapters/persistence/storage/master_key/_master_key.py:346 | no-op | secure-persistence-foundation | low | .vault\adr\2026-04-27-secure-persistence-foundation-adr.md | No-op probe backend is intentionally filtered out prior to provider selection in secure persistence.
src/aeat/adapters/persistence/storage/master_key/_master_key.py:578 | no-op | secure-persistence-foundation | medium | .vault\adr\2026-04-30-secure-persistence-foundation-wave12-adr.md | Master-key key material protection applies platform file-mode behavior where Windows chmod is effectively no-op and POSIX uses 0o700.
src/aeat/adapters/persistence/storage/master_key/_master_key.py:683 | no-op | secure-persistence-foundation | medium | .vault\adr\2026-04-30-secure-persistence-foundation-wave12-adr.md | Chmod target protection for secure master key files is documented as POSIX-only and no-op on Windows.
src/aeat/adapters/persistence/storage/master_key/_master_key.py:820 | placeholder | secure-persistence-foundation | low | .vault\adr\2026-04-30-secure-persistence-foundation-wave17-adr.md | Synthetic placeholder IDs are used as acceptable test values in insecure-mode compatibility and onboarding guidance.
src/aeat/adapters/persistence/storage/master_key/_master_key.py:842 | placeholder | secure-persistence-foundation | low | .vault\adr\2026-04-30-secure-persistence-foundation-wave17-adr.md | Sentinel placeholder handling intentionally shares the same validation path as invalid synthetic values.
src/aeat/adapters/persistence/storage/master_key/_master_key.py:884 | placeholder | secure-persistence-foundation | medium | .vault\adr\2026-04-30-secure-persistence-foundation-wave17-adr.md | Real tax IDs are required to be blocked in insecure provider mode; synthetic placeholder IDs such as 00000000T are documented.
src/aeat/adapters/persistence/storage/master_key/_master_key.py:951 | no-op | secure-persistence-foundation | medium | 2026-04-30-secure-persistence-foundation-research | No-op marker describes intentionally unusable keyring backend handling in secure persistence fallback detection.
src/aeat/adapters/persistence/storage/master_key/_test_master_key.py:120 | legacy | secure-persistence-foundation | medium | .vault\adr\2026-04-27-secure-persistence-foundation-adr.md | Master key errors are carried by compatibility hierarchy in persistence errors with legacy catchers preserved.
src/aeat/adapters/persistence/storage/master_key/_test_master_key.py:521 | no-op | secure-persistence-foundation | low | .vault\adr\2026-04-27-secure-persistence-foundation-adr.md | Keyring backend fallback coverage in secure persistence tests aligns with optional-keyring behavior.
src/aeat/adapters/persistence/storage/master_key/_test_master_key.py:532 | no-op | secure-persistence-foundation | low | .vault\adr\2026-04-27-secure-persistence-foundation-adr.md | Missing keyring package path is handled by secure master-key fallback tests.
src/aeat/adapters/persistence/storage/master_key/_test_master_key.py:540 | no-op | secure-persistence-foundation | low | .vault\adr\2026-04-27-secure-persistence-foundation-adr.md | Simulated no-op keyring backends are covered by secure persistence test harnesses.
src/aeat/adapters/persistence/storage/secret_store/_secret_store.py:130 | compatibility | secure-persistence-foundation | medium | .vault\adr\2026-04-27-secure-persistence-foundation-adr.md | Envelope contract includes schema_version and compatibility handling for file-backed records.
src/aeat/adapters/persistence/storage/sql/_orm.py:15 | TODO | data-storage | low | .vault\adr\2026-04-12-data-storage-adr.md | Inline TODO markers in ORM are documented in data-storage ADR as temporary migration debt for earlier typed schema decisions.
src/aeat/adapters/persistence/storage/sql/_orm.py:56 | TODO | data-storage | low | .vault\adr\2026-04-12-data-storage-adr.md | Outstanding TODO notes document pending migration from str columns to richer JSON schema in storage layer models.
src/aeat/adapters/persistence/storage/sql/_orm.py:87 | TODO | data-storage | low | .vault\adr\2026-04-12-data-storage-adr.md | TODO markers in ORM reflect known follow-up migration debt for storage schema typing.
src/aeat/adapters/persistence/storage/sql/engine.py:38 | no-op | pr28-storage-retro | medium | 2026-04-12-pr28-storage-retro-audit | Existing storage-engine no-op for non-SQLite and in-memory URL handling is documented in the storage retro audit.
src/aeat/adapters/persistence/storage/sql/engine.py:68 | no-op | pr28-storage-retro | medium | 2026-04-12-pr28-storage-retro-audit | SQLite URL no-op guard in engine bootstrap is aligned with the original storage retro scope.
src/aeat/adapters/persistence/storage/sql/engine.py:82 | no-op | pr28-storage-retro | medium | 2026-04-12-pr28-storage-retro-audit | No-op guards for non-SQLite storage URLs in SQL adapter bootstrap
src/aeat/application/auth/_catalogue.py:86 | legacy | unclassified-state | high | 2026-04-18-unclassified-state-adr | Canonical legacy-unclassified alias support retained for migration compatibility
src/aeat/application/filing/_import.py:5 | scaffold | pdf-import | high | 2026-04-20-pdf-import-adr | Draft import scaffold intentionally leaves all casillas as EMPTY until population
src/aeat/application/filing/_import.py:67 | scaffold | pdf-import | high | 2026-04-20-pdf-import-adr | Draft import scaffold intentionally leaves all casillas as EMPTY until population
src/aeat/application/profile/__init__.py:5 | hardcoded | aeat-cli-redesign | medium | 2026-05-03-aeat-cli-redesign-audit | Profile required-key list currently hardcoded in profile-validation surface
src/aeat/application/review/_adapters.py:384 | placeholder | unified-review-queue | high | 2026-04-18-unified-review-queue-adr | Placeholder adapter row is used to emit a synthetic finding when none exists
src/aeat/application/review/_models.py:100 | placeholder | unified-review-queue | high | 2026-04-18-unified-review-queue-adr | Review model allows placeholder row with null source in draft placeholder path
src/aeat/application/review/test_adapters.py:363 | placeholder | unified-review-queue | high | 2026-04-18-unified-review-queue-plan | Tests validate placeholder row on draft status with no findings is expected
src/aeat/application/review/test_adapters.py:364 | placeholder | unified-review-queue | high | 2026-04-18-unified-review-queue-plan | Tests assert pending drafts map to same validated placeholder row
src/aeat/application/review/test_adapters.py:375 | placeholder | unified-review-queue | high | 2026-04-18-unified-review-queue-plan | Tests enforce placeholder status behavior for pending draft paths
src/aeat/application/review/test_models.py:173 | placeholder | unified-review-queue | high | 2026-04-18-unified-review-queue-adr | Model allows None source for placeholder review item in empty-draft case
src/aeat/application/setup/_env_writer.py:204 | compatibility | secure-persistence-foundation | high | 2026-04-30-secure-persistence-foundation-final-security-resolution-audit | Env write guard correctly rejects incompatible master-key path for real tax data
src/aeat/application/setup/_prompter.py:33 | noop | setup-wizard | medium | 2026-04-12-setup-wizard-adr | Prompter intentionally no-ops announce defaults on wrong type inputs
src/aeat/application/setup/test_wizard.py:123 | noop | setup-wizard | medium | 2026-04-12-setup-wizard-adr | Test uses deterministic noop runner as a test-time protocol stub
src/aeat/application/transactions/_diagnostics.py:112 | stub | aeat-cli-redesign | high | 2026-05-03-aeat-cli-redesign-audit | Diagnostics factory intentionally exposes no-op/stub path for CLI-level render contracts
src/aeat/application/workflow/_engine.py:221 | placeholder | workflow-engine | high | 2026-04-12-workflow-engine-adr | Workflow placeholder hash placeholder handling is expected for template run output
src/aeat/application/workflow/_protocols.py:11 | fakes/stubs | auth-protocol | medium | 2026-04-16-submission-safety-sweep-code-review-audit | Workflow protocols enforce strict test doubles policy in protocol-facing contract
src/aeat/application/workflow/test_engine.py:624 | placeholder | aeat-access-gate | high | 2026-04-17-aeat-access-gate-code-review-exec | Access gate cannot be swapped for no-op because call sites expect immutable gating
src/aeat/core/access_gate/__init__.py:17 | no-op | aeat-access-gate | high | 2026-04-17-aeat-access-gate-code-review-exec | No seam exists to replace access gate with a no-op in current hard-cut design
src/aeat/core/access_gate/__init__.py:112 | no-op | aeat-access-gate | high | 2026-04-17-aeat-access-gate-code-review-exec | Live-write branch intentionally requires explicit refusal instead of silent no-op
src/aeat/core/config.py:708 | legacy | (none) | low | (none) | No meaningful vault feature context matched; marker appears local to config validation path
src/aeat/core/config.py:718 | placeholder | (none) | low | (none) | No meaningful vault feature context matched; marker appears local to config placeholder validation
src/aeat/core/config.py:762 | placeholder | (none) | low | (none) | No meaningful vault feature context matched; marker appears local to config placeholder validation
src/aeat/core/env_io.py:73 | no-op | (none) | low | (none) | No meaningful vault feature context matched; marker appears local to env cleanup finalizer
src/aeat/core/errors/_registry.py:234 | placeholder | error-code-registry | high | 2026-04-25-error-code-registry-review-audit | Registry uses placeholder exit-code binding path by design for declared errors
src/aeat/core/json_contract.py:82 | compatibility | json-output-contract | high | 2026-04-25-json-output-contract-adr | schema_version compatibility contract is documented for JSON contract envelope evolution
src/aeat/core/logging.py:67 | placeholder | json-output-contract | medium | 2026-04-25-json-output-contract-adr | Placeholder regex handling in logging scrubber is part of JSON output safety contract
src/aeat/core/logging.py:68 | placeholder | json-output-contract | medium | 2026-04-25-json-output-contract-adr | Logging placeholder parsing supports `%` formatting safely for sanitized redaction contracts.
src/aeat/core/logging.py:105 | placeholder | json-output-contract | medium | 2026-04-25-json-output-contract-adr | This placeholder parsing behavior is part of logging sanitization compatibility checks.
src/aeat/core/logging.py:136 | placeholder | json-output-contract | medium | 2026-04-25-json-output-contract-adr | Placeholder token extraction intentionally aligns with tuple-style logging redaction behavior.
src/aeat/core/logging.py:138 | placeholder | json-output-contract | medium | 2026-04-25-json-output-contract-adr | Sensitive-key scrub lookup maps only positional placeholders by design.
src/aeat/core/observability/_context.py:275 | legacy | run-trace | low | 2026-04-21-run-trace-rolling-audit | Legacy compatibility fields are retained for older trace payloads.
src/aeat/core/observability/_models.py:376 | legacy | run-trace | medium | 2026-04-21-run-trace-rolling-audit | Legacy trace shape support is deliberate to avoid breaking existing trace consumers.
src/aeat/core/observability/_models.py:394 | compatibility | run-trace | medium | 2026-04-21-run-trace-rolling-audit | Compatibility note documents backwards compatibility for pre-field trace payloads.
src/aeat/core/observability/_replay.py:8 | obsolete | run-trace | medium | 2026-04-21-run-trace-rolling-audit | Obsolete CLI behavior is preserved intentionally for migration safety in replay flows.
src/aeat/core/observability/_replay.py:28 | legacy | run-trace | low | 2026-04-21-run-trace-rolling-audit | Legacy CLI flags are retained only as removed/safety compatibility markers.
src/aeat/core/observability/_replay.py:141 | obsolete | run-trace | medium | 2026-04-21-run-trace-rolling-audit | Obsolete replay argument handling path remains compatibility-guarded in tests.
src/aeat/core/observability/test_replay.py:102 | legacy | run-trace | high | 2026-04-21-run-trace-rolling-audit | Tests explicitly construct legacy trace data to validate replay compatibility semantics.
src/aeat/core/observability/test_replay.py:116 | legacy | run-trace | high | 2026-04-21-run-trace-rolling-audit | Legacy trace persistence path is intentionally covered by observability replay tests.
src/aeat/core/observability/test_replay.py:118 | legacy | run-trace | high | 2026-04-21-run-trace-rolling-audit | Replay fixture lookup by legacy run id is part of replay regression coverage.
src/aeat/core/observability/test_replay.py:170 | legacy | run-trace | high | 2026-04-21-run-trace-rolling-audit | Legacy sentinel test ensures replay context ignores placeholder sentinel values.
src/aeat/core/observability/test_replay.py:271 | dummy | run-trace | low | 2026-04-21-run-trace-rolling-audit | Dummy vault-file test data supports replay and storage-path behavior verification.
src/aeat/core/test_logging.py:27 | temporary | (none) | low | (none) | No meaningful vault context matched; marker appears local to logging test setup behavior.
src/aeat/core/test_logging.py:104 | placeholder | (none) | low | (none) | No meaningful vault context matched; marker appears local to logging placeholder test intent.
src/aeat/core/test_logging.py:105 | placeholder | (none) | low | (none) | No meaningful vault context matched; marker appears local to logging test docstring assertions.
src/aeat/core/test_logging.py:132 | placeholder | (none) | low | (none) | No meaningful vault context matched; marker appears local to logging placeholder test intent.
src/aeat/core/test_logging.py:181 | placeholder | (none) | low | (none) | No meaningful vault context matched; marker appears local to logging placeholder test behavior.
src/aeat/domain/attachments/_repository.py:172 | no-op | attachment-service | medium | 2026-04-17-attachment-service-audit | No-op rename is expected for attachment storage safety semantics.
src/aeat/domain/attachments/_repository.py:191 | temporary | attachment-service | high | 2026-04-17-attachment-service-adr | Temporary file strategy is used for attachment repository integrity updates.
src/aeat/domain/attachments/_repository.py:442 | temporary | attachment-service | high | 2026-04-17-attachment-service-audit | Temporary file usage is part of attachment repository write flow hardening.
src/aeat/domain/calculations/registry/_workbook_parity.py:16 | temporary | (none) | low | (none) | No meaningful vault context matched; marker appears local to workbook parity temporary directory handling.
src/aeat/domain/calculations/registry/_workbook_parity.py:427 | temporary | (none) | low | (none) | No meaningful vault context matched; marker appears local to workbook parity temporary path execution.
src/aeat/domain/calculations/registry/_workbook_parity.py:502 | temporary | (none) | low | (none) | No meaningful vault context matched; marker appears local to workbook parity temporary conversion flow.
src/aeat/domain/justificante/_schema.py:49 | legacy | justificante-parser | high | 2026-04-12-justificante-parser-adr | Legacy label optionality is defined by justificante schema migration compatibility.
src/aeat/domain/manuals/_loader.py:7 | temporary | manual-practico | medium | 2026-04-12-manual-practico-adr.md | Tests use temporary-directory fixtures to validate manual loader behavior in isolation, matching the manuals fixture-driven verification path.
src/aeat/domain/manuals/_verify.py:137 | placeholder | manual-practico | medium | 2026-04-12-manual-practico-adr.md | Manual-practico verification uses sentinel placeholders in its reviewer path and remains scoped to that domain workflow.
src/aeat/domain/manuals/_verify.py:153 | no-op | manual-practico | medium | 2026-04-12-manual-practico-adr.md | No-op handling for v1 manual verify behavior is intentional and documented in the manuals validation design.
src/aeat/domain/normatives/test_verify.py:7 | no-op | normatives | medium | 2026-04-12-normatives-adr.md | Normatives test fixture asserts no-op behavior on clean validation input, which is part of normative rule testing.
src/aeat/domain/normatives/test_verify.py:47 | noop | normatives | medium | 2026-04-12-normatives-adr.md | The idempotent clean-transaction behavior in normatives testing documents expected no-op semantics when inputs are valid.
src/aeat/domain/transactions/_models.py:182 | placeholder | transaction-catalogue | medium | 2026-04-14-transaction-catalogue-adr.md | DecisionProvenance placeholder is planned for future typed transaction provenance in the immutable catalogue model contract.
src/aeat/domain/usage_ratios/_model.py:119 | no-op | usage-ratios | medium | 2026-04-21-usage-ratios-adr.md | No-op path for missing ratio override is intended behavior in usage ratio domain persistence model updates.
src/aeat/domain/usage_ratios/test_model.py:97 | no-op | usage-ratios | medium | 2026-04-21-usage-ratios-adr.md | Transaction usage-ratio removal test confirms idempotent behavior when no unset category exists to clear.
src/aeat/entrypoints/cli/_test_doctor.py:46 | placeholder | auth | medium | 2026-04-12-gsuite-bootstrap-adr.md | Doctor tests use a local OAuth client placeholder secret and are intentionally test-only fixtures for helper path coverage.
src/aeat/entrypoints/cli/_test_doctor.py:479 | placeholder | secure-persistence-foundation | high | 2026-04-30-secure-persistence-foundation-wave17-adr.md | Tests write placeholder master key bytes as fixture setup for doctor command safety checks, not for production values.
src/aeat/entrypoints/cli/_test_doctor.py:494 | placeholder | secure-persistence-foundation | high | 2026-04-30-secure-persistence-foundation-wave17-adr.md | Master key migration fixture writes placeholder master.kdf bytes for local doctor helper simulation and error-path checks.
src/aeat/entrypoints/cli/auth/_registry.py:147 | NotImplementedError | auth | high | 2026-04-12-cert-auth-adr.md | Auth provider registry keeps a NotImplementedError compatibility bridge while provider coverage expands.
src/aeat/entrypoints/cli/auth/_render.py:55 | legacy | auth | medium | 2026-04-12-cert-auth-adr.md | Auth render layer retains a legacy token marker path for compatibility with legacy sentinel behavior.
src/aeat/entrypoints/cli/auth/_render.py:165 | no-op | auth | high | 2026-04-21-auth-cli-adr.md | Auth status/logout output no-ops when no session exists and is part of intentional sessionless CLI UX handling.
src/aeat/entrypoints/cli/auth/test_auth_cli.py:345 | noop | auth | high | 2026-04-21-auth-cli-adr.md | Auth CLI explicitly documents logout no-op behavior in sessionless mode for stable user-facing contract.
src/aeat/entrypoints/cli/filing/__init__.py:596 | scaffold | filing-draft-engine | medium | 2026-04-12-filing-draft-engine-adr.md | Import scaffold translation path confirms filing import builds and reports draft scaffolding as documented filing draft output behavior.
src/aeat/entrypoints/cli/financial/ingest.py:117 | legacy | financial | medium | 2026-04-13-p2a-financial-provider-adr.md | Financial ingest preserves legacy stdout-only pipe behavior as compatibility fallback documented for operator workflows.
src/aeat/entrypoints/cli/financial/test_cli.py:160 | legacy | financial | medium | 2026-04-13-p2a-financial-provider-adr.md | Financial CLI test docs legacy stdout-only pipe behavior for compatibility with existing pipe-only tooling.
src/aeat/entrypoints/cli/financial/test_profile.py:280 | placeholder | financial | low | 2026-04-13-p2a-financial-provider-adr.md | Profile placeholder test name documents fixture-oriented profile command behavior and accepted placeholder token path in financial CLI tests.
src/aeat/locales/manager.py:23 | scaffold | trilingual-i18n | medium | 2026-04-12-trilingual-i18n-adr.md | Locale manager provides scaffolding and structural health for locale file and translation bundle management.
src/aeat/locales/manager.py:94 | scaffold | trilingual-i18n | medium | 2026-04-12-trilingual-i18n-adr.md | Locale manager scaffold method is part of i18n bootstrap and structural health behavior in locale management feature scope.
tests/_marker_hook.py:27 | noop | pytest-markers | high | 2026-04-17-pytest-markers-adr.md | Marker hook comment documents identical marker sets as intentional no-op behavior for test collection compatibility.
tests/_marker_hook.py:70 | compat | pytest-markers | high | 2026-04-17-pytest-markers-adr.md | Older pytest compatibility note documents legacy test marker behavior kept for supported runtime compatibility.
tests/fixtures/pdf_corpus/__init__.py:1 | scaffold | pdf-import | medium | 2026-04-20-pdf-import-adr.md | PDF corpus fixture package module text documents fixture scaffolding for generated corpus imports and pipeline setup.
tests/import_contract/adapters/inbound/justificante/test_parser.py:246 | dummy | pdf-import | medium | 2026-04-20-pdf-import-adr.md | Dummy PDF fixture filename supports import contract tests for justificante parser fixtures under the PDF ingestion test surface.
tests/import_contract/domain/transactions/test_catalogue.py:441 | no-op | transaction-catalogue | medium | 2026-04-14-transaction-catalogue-adr.md | No-op classification idempotence test documents expected behavior for reclassification attempts in transaction catalogue updates.
tests/test_config.py:140 | placeholder | (none) | low | (none) | No matching vault feature context was found; marker appears local to config template validation and test-doc paths.
```

## Recommendations

Review each row for intent before cleanup; some compatibility or fallback language may describe valid production behavior rather than removable scaffolding.
