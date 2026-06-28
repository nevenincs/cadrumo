---
tags:
  - '#audit'
  - '#test-tautology'
date: '2026-05-05'
modified: '2026-05-05'
related: []
---



# `test-tautology` audit: `python test sweep`

## Scope

Read-only mechanical audit of every `_test_*.py` and `test_*.py` under `src/` and `tests/` on 2026-05-05.

Audit surface: 237 Python test files, partitioned into six chunks of ~40 files each, audited concurrently by six sonnet workers.

Three marker categories:

- `tautology`: assertions where test and production invoke the same function with the same input, so the comparison can never fail.
- `hardcoded-english`: assertions that pin English copy emitted by `tr()`, regressing the project's i18n contract.
- `dev-meta`: tests encoding development cadence (phase / wave / task / in-flight) instead of behaviour.

Row format: `file:line | marker | short reference`.

Findings count: 35 across 237 files (zero `dev-meta`).

## Findings

Rows below are generated from `.tmp/codebase-sanitization-findings.sqlite3`.

```text
file:line | marker | short reference
src/aeat/adapters/inbound/sanitizer/test_records.py:53 | tautology | nif-synthetic-roundtrip | assert replacement.synthetic == "Y0000001S" # after constructing NifReplacement(synthetic="Y0000001S")
src/aeat/adapters/inbound/sanitizer/test_records.py:62 | tautology | nif-synthetic-roundtrip-2 | assert replacement.synthetic == "12345678Z" # after NifReplacement(synthetic="12345678Z")
src/aeat/adapters/inbound/sanitizer/test_records.py:90 | tautology | name-synthetic-roundtrip | assert record.synthetic == "APELLIDO APELLIDO NOMBRE" # after NameReplacement(synthetic="APELLIDO APELLIDO NOMBRE")
src/aeat/adapters/inbound/sanitizer/test_records.py:118 | tautology | expediente-synthetic-roundtrip | assert record.synthetic == "9999202400000001" # after ExpedienteReplacement(synthetic="9999202400000001")
src/aeat/adapters/inbound/sanitizer/test_records.py:138 | tautology | csv-synthetic-roundtrip | assert record.synthetic == "SANITIZED1002021" # after CsvReplacement(synthetic="SANITIZED1002021")
src/aeat/adapters/inbound/sanitizer/test_records.py:166 | tautology | nrc-synthetic-roundtrip | assert record.synthetic == "0000000000000XXXXXXXXX" # after NrcReplacement(synthetic=...)
src/aeat/adapters/inbound/sanitizer/test_records.py:187 | tautology | iban-synthetic-roundtrip | assert record.synthetic == "ES8023100001180000012345" # after IbanReplacement(synthetic=...)
src/aeat/adapters/inbound/sanitizer/test_records.py:207 | tautology | importe-synthetic-roundtrip | assert record.synthetic == "1.000,00" # after ImporteReplacement(synthetic="1.000,00")
src/aeat/adapters/inbound/sanitizer/test_records.py:215 | tautology | importe-neg-synthetic-roundtrip | assert record.synthetic == "-1.000,00" # after ImporteReplacement(synthetic="-1.000,00")
src/aeat/adapters/inbound/sanitizer/test_records.py:243 | tautology | arbitrary-synthetic-roundtrip | assert record.synthetic == "SANITIZED-OPAQUE" # after ArbitraryReplacement(synthetic="SANITIZED-OPAQUE")
src/aeat/adapters/inbound/sanitizer/test_records.py:263 | tautology | address-synthetic-roundtrip | assert record.synthetic == "CALLE CALLE 0 0 CIUDAD (PROVINCIA)" # after AddressReplacement(synthetic=...)
src/aeat/adapters/outbound/aeat/export/test_errors.py:45 | tautology | translatable-message-roundtrip | assert exc.translated_message == translatable # translatable passed directly to constructor 2 lines above
src/aeat/adapters/outbound/aeat/export/test_models.py:172 | tautology | make-submission-id-self-equal | assert make_submission_id("draft-1", 1) == make_submission_id("draft-1", 1)
src/aeat/adapters/outbound/llm/_test_cache.py:40 | tautology | llm-cache-key-self-equal | assert cache.build_key(request, LLMProvider.ANTHROPIC, "claude-sonnet-4-6") == cache.build_key(request, ...)
src/aeat/adapters/outbound/llm/test_smoke.py:21 | tautology | llm-smoke-logger-name-self | assert logging.get_logger(__name__).name == __name__
src/aeat/adapters/persistence/storage/test_smoke.py:27 | tautology | storage-smoke-logger-name-self | assert logging.get_logger(__name__).name == __name__
src/aeat/application/auth/test_catalogue.py:52 | tautology | list-auth-providers-vs-catalogue | assert list_auth_providers() == AUTH_PROVIDER_CATALOGUE # production returns the constant directly
src/aeat/application/profile/test_validate.py:114 | tautology | list-profile-key-records-vs-profile-keys | assert records == PROFILE_KEYS # list_profile_key_records() returns PROFILE_KEYS directly
src/aeat/core/errors/test_envelope.py:83 | tautology | envelope-message-vs-tr-key | assert envelope.message == expected # both sides call tr(code.message_key) under same _output_language ctx
src/aeat/domain/normatives/test_schema.py:58 | hardcoded-english | test-schema-titulo-reducciones | assert articulo.titulo == "Reducciones" # constructed with i18n key titulo_908834
src/aeat/entrypoints/cli/_test_doctor.py:528 | hardcoded-english | argon2id-tr-detail | assert "Argon2id" in row.detail # detail=tr(cli.doctor.details.master_kdf_argon2id)
src/aeat/entrypoints/cli/auth/test_auth_cli.py:349 | hardcoded-english | no-active-session-tr | assert "no active session" in result.output # production: tr(cli.auth.init.errors.no_session_found)
src/aeat/entrypoints/cli/auth/test_auth_cli.py:365 | hardcoded-english | signed-out-of-tr | assert "Signed out of" in result.output # production: tr(cli.auth.init.errors.signed_out)
src/aeat/entrypoints/cli/financial/test_profile.py:70 | hardcoded-english | profile-no-ratios-msg | assert "No usage ratios configured." in result.output
src/aeat/entrypoints/cli/financial/test_profile.py:76 | hardcoded-english | profile-set-ratio-confirm-msg | assert "set suministros_home_office_luz = 0.21" in set_result.output
src/aeat/entrypoints/cli/financial/test_profile.py:128 | hardcoded-english | profile-ineligible-category-msg | assert "does not accept a usage ratio" in result.output
src/aeat/entrypoints/cli/financial/test_profile.py:141 | hardcoded-english | profile-must-be-finite-msg | assert "must be finite" in result.output
src/aeat/entrypoints/cli/financial/test_profile.py:153 | hardcoded-english | profile-invalid-ratio-msg | assert "invalid ratio" in result.output
src/aeat/entrypoints/cli/financial/test_profile.py:160 | hardcoded-english | profile-unknown-key-msg | assert "unknown key" in result.output
src/aeat/entrypoints/cli/financial/test_profile.py:172 | hardcoded-english | profile-did-you-mean-msg | assert "did you mean" in result.output
src/aeat/entrypoints/cli/financial/test_profile.py:241 | hardcoded-english | profile-eligible-categories-label | assert "eligible categories:" in result.output
src/aeat/entrypoints/cli/financial/test_profile.py:252 | hardcoded-english | profile-unset-confirm-msg | assert "unset suministros_home_office_luz" in unset_result.output
src/aeat/entrypoints/cli/financial/test_profile.py:256 | hardcoded-english | profile-no-user-ratio-msg | assert "no user ratio set for suministros_home_office_luz" in second_unset.output
src/aeat/entrypoints/cli/test_registry_cli.py:370 | hardcoded-english | registry-verify-filed-state-help-spanish | assert "estado presentado capturado" in result.output # AEAT_OUTPUT_LANGUAGE=en but Spanish tr() content
src/aeat/entrypoints/cli/test_registry_cli.py:383 | hardcoded-english | registry-capture-source-help-spanish | assert "observaciones fuente presentadas" in result.output # hardcoded tr() translated content
```

## Context Cross-References

Rows below are generated from `.tmp/codebase-sanitization-findings.sqlite3` context records.

```text
file:line | marker | feature | confidence | vault refs | possible cause/context
No feature or vault context recorded yet.
```

## Recommendations

Triage each finding before any cleanup; the marker captures a *suspicion*, not a verdict. Three response patterns are reasonable:

- For `tautology` rows where the assertion is part of a broader determinism + distinctness suite (e.g. `make_submission_id(x, y) == make_submission_id(x, y)` next to `... != make_submission_id(x, z)`), the bare round-trip is a deliberate documentation aid and may stay.
- For standalone `tautology` rows (`record.synthetic == "..."` after `record = Cls(synthetic="...")`, `tr(key)` on both sides), prefer dropping the assertion and letting the constructor's lack of `pytest.raises`, or the surrounding state assertion, carry the contract.
- For `hardcoded-english` rows, replace the substring/equality check with a behavioural assertion (state, exit code, branch distinctness). Comparing against `tr(key)` would be a tautology because both sides resolve to the same key path.
