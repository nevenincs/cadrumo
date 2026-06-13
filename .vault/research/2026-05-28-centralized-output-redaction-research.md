---
tags:
  - '#research'
  - '#centralized-output-redaction'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-04-25-json-output-contract-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]'
  - '[[2026-05-27-secure-storage-repair-profile-privacy-review-audit]]'
---

# `centralized-output-redaction` research: `CLI and diagnostic output redaction centralization`

This research maps the existing redaction, logging, error, observability, and CLI-output surfaces so the secure-storage privacy hardening work can move from command-local scrubbing to a central output architecture.

## Findings

The codebase already has several redaction mechanisms, but they are not enrolled through a single output boundary.

- `src/aeat/core/redaction/__init__.py` provides policy-based `redact`, `redact_structured`, `redact_for_log`, and sensitivity-class rule resolution.
- `src/aeat/core/logging.py` provides `SecretScrubbingFilter` and installs log-record scrubbing for configured handlers.
- `src/aeat/core/observability/_sink.py` and `src/aeat/core/observability/_store.py` call `redact_structured` before persisting diagnostic run traces and event logs.
- `src/aeat/core/errors/_registry.py` has a separate sensitive-context scrubber for error envelopes.
- `src/aeat/core/output_rendering.py` serializes JSON and joins text lines, but does not redact payloads or text output.
- `src/aeat/entrypoints/cli/_common.py` centralizes `_emit` and `_emit_envelope`, but those helpers delegate to output rendering without a redaction policy.

The result is duplicated and inconsistent:

- Logging uses a hard-coded key and regex scrubber.
- Error rendering uses a separate context scrubber.
- Observability uses sensitivity-class redaction rules.
- Auth diagnostics implements bespoke `_redacted_ref` and `_redacted_url_summary` helpers.
- Repair and profile CLI commands have command-local redaction patches.

## CLI Output Inventory

Production CLI and diagnostics modules with output surfaces:

- `src/aeat/diagnostics/profile.py`
- `src/aeat/diagnostics/secure_objects.py`
- `src/aeat/entrypoints/cli/__init__.py`
- `src/aeat/entrypoints/cli/_app_live.py`
- `src/aeat/entrypoints/cli/_common.py`
- `src/aeat/entrypoints/cli/_config/__init__.py`
- `src/aeat/entrypoints/cli/_config/_google.py`
- `src/aeat/entrypoints/cli/_config/_profile_census.py`
- `src/aeat/entrypoints/cli/_errors.py`
- `src/aeat/entrypoints/cli/_exit_codes.py`
- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/_overview.py`
- `src/aeat/entrypoints/cli/_registry_corpus.py`
- `src/aeat/entrypoints/cli/_review.py`
- `src/aeat/entrypoints/cli/registry.py`

Mechanical scan results:

- `_emit` call sites: 198.
- `_emit_envelope` call sites: 12.
- direct `typer.echo` call sites: 13, including diagnostics and error/help paths.
- direct `print` or `console.print` production CLI output: none in the scanned surface.
- direct stderr/write paths remain in startup and error-boundary helpers.

Sensitive terms observed in output modules include `profile_id`, `bucket_id`, `active_profile`, `tax_id`, `nif`, `object_key`, `url`, `token`, `certificate`, `password`, `passphrase`, and `session`.

## Affected Implementation Surface

Core and shared output files:

- `src/aeat/core/redaction/__init__.py`
- `src/aeat/core/classification/__init__.py`
- `src/aeat/core/output_rendering.py`
- `src/aeat/core/json_contract.py`
- `src/aeat/core/logging.py`
- `src/aeat/core/errors/_registry.py`
- `src/aeat/core/errors/registry/_application.py`
- `src/aeat/core/errors/registry/_domain.py`
- `src/aeat/core/observability/_redaction_rules.py`
- `src/aeat/core/observability/_sink.py`
- `src/aeat/core/observability/_store.py`

Application and diagnostics files with existing bespoke redaction or privacy-sensitive reports:

- `src/aeat/application/auth/_diagnostics.py`
- `src/aeat/application/auth/_operator.py`
- `src/aeat/application/diagnostics.py`
- `src/aeat/application/live/__init__.py`
- `src/aeat/application/repair_integrity.py`
- `src/aeat/application/workflow/_profile_health.py`

CLI command files with sensitive output paths:

- `src/aeat/entrypoints/cli/_common.py`
- `src/aeat/entrypoints/cli/_errors.py`
- `src/aeat/entrypoints/cli/__init__.py`
- `src/aeat/entrypoints/cli/_app_live.py`
- `src/aeat/entrypoints/cli/_config/__init__.py`
- `src/aeat/entrypoints/cli/_config/_google.py`
- `src/aeat/entrypoints/cli/_config/_profile_census.py`
- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/entrypoints/cli/_overview.py`
- `src/aeat/entrypoints/cli/_overview_rendering.py`
- `src/aeat/entrypoints/cli/_registry_corpus.py`
- `src/aeat/entrypoints/cli/_review.py`
- `src/aeat/entrypoints/cli/_root_landing.py`
- `src/aeat/entrypoints/cli/_schemas.py`
- `src/aeat/entrypoints/cli/_modelo_payloads.py`
- `src/aeat/entrypoints/cli/_review_payloads.py`
- `src/aeat/entrypoints/cli/registry.py`
- `src/aeat/diagnostics/profile.py`
- `src/aeat/diagnostics/secure_objects.py`

## Existing Verification Surface

Useful existing tests:

- `src/aeat/core/test_logging.py`
- `src/aeat/core/test_output_rendering.py`
- `src/aeat/core/errors/test_envelope.py`
- `src/aeat/core/observability/test_sink_redaction.py`
- `src/aeat/core/observability/test_store_redaction.py`
- `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- `src/aeat/entrypoints/cli/test_json_schema_conformance.py`
- `src/aeat/entrypoints/cli/test_error_boundary_integration.py`
- `src/aeat/entrypoints/cli/test_error_boundary_unwrap.py`
- `src/aeat/application/auth/test_diagnostics.py`
- `src/aeat/application/auth/test_operator.py`
- `src/aeat/application/live/test_iva_wallet_privacy_static_guard.py`
- `src/aeat/adapters/outbound/llm/test_redaction.py`
- `src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`

## Recommendation

Centralize redaction policy in `src/aeat/core/redaction/__init__.py` and make `src/aeat/core/output_rendering.py` the mandatory CLI success-output redaction boundary. `_emit`, `_emit_envelope`, and JSON-envelope emission should call this boundary, and direct `typer.echo` output should be either migrated to `_emit` or explicitly declared as a non-sensitive diagnostic exception.

The central policy needs transport profiles:

- CLI public output: profile/bucket/object keys become stable placeholders or digests; NIF, token, URL path, cookie, and passphrase values are redacted.
- Log/error output: existing log redaction semantics remain but use shared rule definitions.
- Diagnostic/run trace output: continue using structured diagnostic redaction rules.

The rollout must keep an inventory gate so new output call sites cannot bypass the central boundary unnoticed.
