---
tags:
  - '#audit'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-final-security-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave7-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave6-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave5-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-adr]]"
  - "[[2026-04-30-secure-persistence-foundation-audit]]"
---



# `secure-persistence-foundation` final security audit — resolution | (**status:** `resolved`)

## Scope

Resolution of the eight HIGH/MEDIUM findings raised in the final
security audit gate. Every finding is now closed by routing the
matching plaintext writer through the substrate's
`save_encrypted_envelope` helper at the policy-mandated sensitivity
class. Storage imports stayed deferred to preserve json-pipe-safety,
all tests use real on-disk persistence with an
`EphemeralMasterKeyProvider`, and `default_rotation_plan` was
extended so master-key rotation covers every new HKDF-context bearer.

## Verification

- `uv run --no-sync ruff check src/aeat`: **all checks passed**.
- `uv run --no-sync ty check src/aeat/storage src/aeat/financial src/aeat/entrypoints/cli/financial src/aeat/entrypoints/cli/security.py src/aeat/observability src/aeat/sync src/aeat/setup`: **all checks passed**.
- `uv run --no-sync python -m pytest src/aeat -q --ignore=src/aeat/aeat-verify -m "unit and not live_read and not live_write"`:
  **3829 passed, 18 skipped, 21 deselected, 3 failed**. The three
  remaining failures (`cli/workflow/test_cli.py::TestWorkflowCli::test_next_json_round_trips`
  and the two `mcp/test_launch_google_workspace.py::TestLauncherBoundary`
  cases) reproduce on the pre-resolution baseline (verified via
  `git stash` + rerun) and are unrelated to the resolution work; they
  pre-date this PR.

## Resolution table

| Finding | Severity | Resolution |
| --- | --- | --- |
| LEAK-001 | HIGH | `aeat financial txs build/classify/classify-llm` now route every read and write through `TransactionCatalogueRepository`. The plaintext `save_transactions` / `load_transactions` helpers are deleted from `src/aeat/domain/financial/transactions/_service.py`, removed from the `aeat.domain.financial.transactions` public surface, and all twelve test files that previously exercised the legacy path now seed catalogues through the repository under an `EphemeralMasterKeyProvider`. Wave-3 docstring at `src/aeat/domain/financial/transactions/_repository.py:1-21` is updated to reflect the strict-ciphertext-only state. |
| LEAK-002 | HIGH | New `InvoiceCatalogueRepository` at `src/aeat/domain/financial/invoices/_repository.py` mirrors the transaction repository surface at FINANCIAL class with HKDF context `aeat.domain.financial.invoices.catalogue.v1`. The plaintext `save_invoices` / `load_invoices` helpers are removed from `src/aeat/domain/financial/invoices/_service.py`. `link_transaction_bidirectional` now takes store directories (rather than legacy file paths) and routes both reads and writes through the repositories; the byte-level invoice rollback on transaction-write failure is preserved against the encrypted envelope file. New test file `src/aeat/domain/financial/invoices/_test_repository.py` covers the round-trip, ciphertext-on-disk canary, foreign-class refusal, foreign-HKDF-context refusal, and idempotent re-save. |
| LEAK-003 | HIGH | `AttachmentStore.write_manifest` (`src/aeat/domain/financial/attachments/_store.py:281`) now writes the manifest as a `CipherEnvelope` at FINANCIAL class with HKDF context `aeat.domain.financial.attachments.manifest.v1`; the manifest filename moves from `<digest>.json` to `<digest>.envelope.json` with a per-record `<digest>.lock` sidecar guarding the write. `load_manifest` and `iter_manifests` are updated to consume the encrypted form. The plaintext `_atomic_write_text` helper is removed. The blob bytes still go through `EncryptedBlobStore` unchanged. |
| LEAK-004 | HIGH | `write_profile_file` at `src/aeat/application/setup/_env_writer.py` now routes the operator's `AutonomoProfile` through `save_encrypted_envelope` at IDENTITY class with HKDF context `aeat.application.setup.profile.v1`. A matching `load_profile_envelope` helper rounds trips out and is consumed by `aeat deadlines` (via `src/aeat/entrypoints/cli/deadlines/_helpers.py::load_profile`), `aeat workflow` (via `src/aeat/application/filing/runtime.py::load_default_filing_profile`), and the setup verifier. The setup wizard test fixture installs an `EphemeralMasterKeyProvider` at IDENTITY class so the wizard can mint the envelope before any production secret store exists. |
| TRACE-001 | MEDIUM | `save_trace` and `save_events_append` at `src/aeat/core/observability/_store.py` now route every record through `redact_structured` against `default_rules_for_class(SensitivityClass.DIAGNOSTIC)` before serialisation, mirroring the existing `JsonlRunSink.emit` discipline. Storage imports are resolved on first use and cached so each emit pays the rule-set cost once. New test file `src/aeat/core/observability/test_store_redaction.py` confirms NIF / bearer-token / URL-path canaries do not survive in the on-disk `trace.json` or `events.jsonl`. |
| LEAK-005 | MEDIUM | `JsonFileDivergenceRepository.save/load/list` at `src/aeat/application/sync/_repository.py` now write a `CipherEnvelope` per record at AUDIT class with HKDF context `aeat.application.sync.divergence.v1`; the on-disk filename is `<record_id>.envelope.json` with a `<record_id>.lock` sidecar guarding each write. Storage imports are deferred behind every method that consults them so the sync subpackage does not pull `aeat.adapters.persistence.storage` into the CLI's startup chain. New test `test_divergence_envelope_is_ciphertext_at_audit_class` confirms the on-disk record is a cipher envelope and contains no plaintext canary. |
| USAGE-001 | MEDIUM | `save_usage_ratios` / `load_usage_ratios` at `src/aeat/domain/financial/usage_ratios/_service.py` now route through the substrate at FINANCIAL class with HKDF context `aeat.domain.financial.usage_ratios.profile.v1`. The plaintext atomic-replace path is removed. Tests in `src/aeat/domain/financial/usage_ratios/test_service.py` are rewritten to exercise the encrypted-envelope round-trip, ciphertext-on-disk canary, and corrupt-envelope error path under an `EphemeralMasterKeyProvider`. |
| DOCSTRING-001 | MEDIUM | The wave-3 stale "legacy fallback" language is removed from both `src/aeat/domain/financial/transactions/_repository.py:1-21` and `src/aeat/application/filing/_repository.py:1-19`. Both docstrings now describe the strict-ciphertext-only state established by the wave-9 hard cutover. |
| LOW-002 | LOW | `default_rotation_plan` in `src/aeat/adapters/persistence/storage/_rotation.py` carries an inline comment block above the two `aeat.application.filing.amendment.v1` entries explaining that one consumer identity binds two sibling subdirectories (`amendment-results/` and `amendments/`) and that deduplicating either entry would break rotation for the corresponding directory. |

LOW-001 (centralise `_validate_*_id` helpers) is **deferred** as a
follow-up: the per-repository validators are already hardened against
path-traversal and uppercase-NTFS-case attacks, the `resolve_record_json_path`
helper is consumed by the workflow + divergence repositories, and the
remaining migration is a code-quality improvement rather than a
security bug. Moving every helper to `_paths` would touch every
governance repository in this PR, which is out of scope for the
final-audit-gate resolution. Tracking issue: TBD.

## Rotation-plan extension

`default_rotation_plan(settings)` now lists thirteen
`RotationPlanEntry` records covering every governance consumer
(transactions, drafts, submissions, amendment-results, amendments,
justificantes, filing history, workflow runs) plus the seven new
HKDF contexts introduced or migrated by this resolution:

- `aeat.domain.financial.invoices.catalogue.v1` (LEAK-002).
- `aeat.domain.financial.attachments.manifest.v1` (LEAK-003).
- `aeat.domain.financial.usage_ratios.profile.v1` (USAGE-001).
- `aeat.application.sync.divergence.v1` (LEAK-005).
- `aeat.application.setup.profile.v1` (LEAK-004).

The two amendment store dirs share a single HKDF context per the
existing design; the inline comment in the rotation plan now flags
that arrangement so a future maintainer does not deduplicate.

## Test discipline

Every new and updated test exercises the encrypted-envelope path
against real on-disk persistence under an
`EphemeralMasterKeyProvider`. No mocks, stubs, fakes, or skips were
introduced. The `test_json_pipe_safety` workflow case now seeds the
profile envelope through the file-backed master-key provider with a
deterministic passphrase so the parent (test) and child (subprocess
CLI) processes derive the same key — this is the only sanctioned
divergence from the in-process `EphemeralMasterKeyProvider` pattern,
and is required because the subprocess inherits only environment
variables, never the parent's process-global override.

## Decision

**Status: RESOLVED.**

Every HIGH and MEDIUM finding is closed. The three remaining
failures in the unit suite (workflow run-trace persistence, MCP
launcher subprocess wiring) reproduce on the pre-resolution baseline
and are tracked separately. `default_rotation_plan` covers every
HKDF-context bearer in the codebase. No plaintext FINANCIAL,
IDENTITY, or AUDIT-class record lands on disk anywhere outside the
encrypted-envelope substrate.
