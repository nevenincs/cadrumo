---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S63'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# live-iva-compensation-wallet W07.P17.S63

Scope: privacy hardening for live IVA diagnostics and acquisition manifests.

## Description

- Audit wallet diagnostic dumps, live acquisition manifests, and remote-state reload summaries for private-value persistence risks.
- Tighten live IVA acquisition failure-context redaction so diagnostic rules apply to persisted context strings.
- Hash sensitive-key failure-context values such as DNI/NIE, support number, profile id, bucket/object keys, credentials, and tokens before report and manifest persistence.
- Hash string elements in generic failure-context sequences to prevent private values from leaking through ambiguous list fields.
- Add a production-path regression that persists a `SedeNavigationError` acquisition manifest through profile-local secure SQL and proves non-private canaries do not appear in report JSON, manifest JSON, remote-state JSON, or database bytes.
- Re-run wallet diagnostic dump coverage proving structural diagnostics do not write raw HTML, screenshots, input values, or wallet amounts.

## Outcome

Live IVA acquisition reports and persisted manifests now redact failure-context values at the central acquisition boundary before storage. Operational fields such as phone state and redacted URL host remain available for debugging, while identity, support-number, profile/storage references, token-like values, and ambiguous sequence strings are reduced to stable hashed evidence refs.

Verification passed:

- `python -m pytest -q src/aeat/application/live/test_iva_remote_state_acquisition.py::test_acquisition_manifest_redacts_sensitive_surface_failure_context src/aeat/application/live/test_iva_remote_state_acquisition.py::test_acquisition_manifest_persists_redacted_auth_diagnostic_ref src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py::test_wallet_diagnostic_dump_writes_only_redacted_structural_summary`
- `python -m pytest -q src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/application/live/test_filed_capture_calculation_history.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`
- `python -m ruff check src/aeat/application/live/__init__.py src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`

## Notes

The first focused S63 run failed because a support-number canary nested in a generic `attempts` sequence was still persisted. The fix intentionally hashes persisted sequence strings at this diagnostic boundary. No live AEAT request was made by this privacy regression. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.
