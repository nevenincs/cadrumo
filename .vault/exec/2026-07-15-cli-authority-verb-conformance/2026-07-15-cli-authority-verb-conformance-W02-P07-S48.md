---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S48'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Make the active certificate credential resolver and named-source certificate check use only selected-profile secure storage with explicit fail-closed absence, and make ordinary certificate-secret set/remove crash-resumable through one secret-free durable intent or outbox carrying a stable operation id, event kind and timestamp, prior-presence state, and non-secret completion witness, resuming pending mutations before accepting a new mutation without migration, fallback, probing, reconciliation, or a parallel secret writer

## Scope

- `src/cadrumo/application/auth/_certificate_sources_operator.py`
- `src/cadrumo/application/auth/_certificate_secret_backend.py`
- `src/cadrumo/adapters/persistence/storage/secret_store/_secret_store.py`
- `src/cadrumo/application/auth/tests/test_certificate_sources_check.py`

## Description

- Ground the named-source check, active credential resolver, secure-storage backend, and governing certificate decision with directed Vaultspec-RAG code and ADR searches.
- Remove the check-specific global-password fallback and project each named source's secure-storage secret, including explicit absence, into an isolated settings value.
- Reuse one private fail-closed named-secret helper from both the registry check and active credential resolver so storage-error policy has one declaration.
- Treat real secure-storage read failures as absent named credentials so the health probe fails closed instead of inheriting a global password.
- Rebind existing valid, expiring, expired, and multi-source health tests to real encrypted per-source secrets.
- Add adverse real-behavior coverage in which the global password is exactly capable of opening the PKCS#12 but the named source has no bound secret.
- Corrupt the real encrypted secret-store index after binding a source secret and prove the read failure also cannot activate the valid global password.
- Prove an unselected named registration preserves the exact legacy global path, password, and friendly name.
- Preserve the already-landed single-writer, durable certificate-secret mutation authority from the earlier S48 prerequisite commits without changing its backend, store, or recovery paths.

## Outcome

- `check_operator_certificate_sources` now uses only the selected profile's `SecureStorageCertificateSecretBackend` value for every registered named source.
- Missing and unreadable named-source secrets reach `_probe_certificate_bundle` as an explicit `None`; the global single-certificate password remains available only outside the named-source registry path.
- Caller-supplied settings remain intact for warning thresholds, certificate backend, friendly name, and other probe policy because only the password field is copied.
- The mutation-sensitive missing-secret node passed: 1 test.
- The complete certificate-source check module passed: 13 tests.
- Focused Ruff passed with no findings, and `git diff --check` passed.
- The path-scoped feature gate passed Ruff and the complete designated test module.
- The feature index was regenerated, and the feature-scoped Vault check passed every check with no warnings.
- Directed semantic and exact-source duplication searches found one public check caller, one public raw named-secret read seam, one shared fail-closed read-policy helper, and one secure-storage backend; no second named-source password fallback or parallel secret writer was introduced.
- The final fresh import graph analyzed 3,432 files and 16,272 dependencies. Four contracts were kept; the layered contract was blocked only by the newly landed reset commit importing `cadrumo.adapters.persistence.storage.bucket` from `cadrumo.application.config_reset`.

## Notes

- The import-linter failure is outside the S48 path set and was reproduced after the reset work landed as commit `60135859e2`. This change removes an application import of `override_settings` and adds no application-to-adapter dependency.
- The plan structural check reported only the existing intentional non-monotonic Step-order warning.
- The plan row also names the durable set/remove mutation work already landed in `27d8bc5404` and its real CLI recovery proof in `84c435bb94`; this prompt-run closes the remaining named-source check fallback defect without reopening those paths.
- No fake, mock, stub, patch, monkeypatch, skip, xfail, mirrored business logic, data loss, or unrelated-path edit was introduced.
