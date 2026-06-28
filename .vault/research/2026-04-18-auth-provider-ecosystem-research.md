---
tags:
  - "#research"
  - "#cert-provider"
date: "2026-04-18"
modified: '2026-04-18'
related:
  - "[[2026-04-12-cert-auth-adr]]"
  - "[[2026-04-18-auth-provider-abstraction-adr]]"
  - "[[2026-04-18-cert-provider-migration-adr]]"
---

# cert-provider research: auth-provider-ecosystem-audit

Comprehensive audit and research of the `AuthProvider` ecosystem following the migration to a provider-agnostic abstraction (Issue #282). This document evaluates security, robustness, network handling, and the extensibility of the current protocol for Cl@ve support.

## Findings

### 1. Code Security & Secret Isolation

The audit confirms that the `AuthProvider` implementation and its supporting models strictly adhere to the "no-leak" mandate:

*   **Secret Protection**: `LoadedCertificate` (in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_providers/_certificate/certificate.py`) utilizes `pydantic.PrivateAttr` for `_pkcs12_bytes`, `_password`, and `_private_key_handle`. These fields are excluded from `model_dump()`, `model_dump_json()`, and `repr()`.
*   **Metadata Safety**: The `AeatAuthenticator._capture_storage_state_locked` method persists a `.meta.json` sidecar. Audit confirms this sidecar only contains the certificate thumbprint, subject, NIF, and handshake timestamps/results. No private key material or passphrases are persisted.
*   **Logging**: Review of `load_certificate` and `authenticate` logs shows only public identifiers (thumbprint, subject, NIF) are recorded.
*   **File Hardening**: The `_restrict_file_permissions` utility in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py` implements OS-specific hardening:
    *   **Windows**: Uses `icacls.exe` to strip inheritance and grant full control only to the current user (via `getpass.getuser()` and `USERDOMAIN` environment variables).
    *   **POSIX**: Uses `os.chmod(path, 0o600)`.
    *   **Edge Case**: If `icacls` fails or is unavailable, the system logs a warning but continues. This is acceptable as a best-effort hardening, but could be elevated to a failure in high-security environments.

### 2. Robustness & Resource Cleanup

The ecosystem exhibits high resilience to partial failures and resource leaks:

*   **Context Leakage**: `AeatAuthenticator.authenticate` and `resume_from_storage_state` implement `try...except` blocks that explicitly call `_close_browser_session` and `_drop_context` on failure.
*   **Atomic Writes**: The `_write_json_atomic` method uses `tempfile.NamedTemporaryFile` within the target directory, ensuring that a disk-full or interrupt condition during write leaves the original file (if any) intact and prevents partial JSON corruption. The use of `os.replace` ensures atomic commitment of the new state.
*   **In-flight Protection**: `AeatAuthenticator` uses an internal counter (`_inflight_pages`) and an `asyncio.Event` (`_inflight_drained`) to ensure `close()` waits for all active verification pages to terminate before tearing down the browser context.

### 3. Network & Condition Handling

Current implementations of `verify()` and `handshake` are functional but lack granular control:

*   **Timeouts**: The navigation timeout is hardcoded to 30,000ms (`AEAT_LOGIN_NAVIGATION_TIMEOUT_MS`). While appropriate for standard Spanish government portal latency, it is not configurable per-provider or via environment variables.
*   **Retry Policy**: There is currently no retry logic for intermittent network failures (e.g., DNS glitches or AEAT gateway timeouts) during `verify()`.
*   **Error Reporting**: `AeatLoginAssertion` correctly captures and surfaces `error_message` and `status_code`, allowing the caller to distinguish between a "Rejected Certificate" (403) and a "Network Timeout".

### 4. Proactive Certificate Health

While the `CertificateHealth` model and `evaluate_loaded_certificate_health` logic are robust, they are underutilized:

*   **Gap**: `AeatAuthenticator.authenticate()` calls `load_certificate()`, which raises `CertificateExpiredError` for hard expiries. However, it does not check the "WARN" or "CRITICAL" thresholds before proceeding.
*   **Recommendation**: Integrate a proactive health check into the `authenticate()` flow. If a certificate is in the `CRITICAL` window, the authenticator should optionally raise `CertificatePreExpiryError` to warn Kent before he attempts a login that might fail shortly after.

### 5. Cl@ve Provider Research & Abstraction Readiness

Research into Cl@ve (Permanente, Móvil, PIN) login flows reveals a significant difference from Certificate-based auth:

*   **Multi-Step Interactivity**:
    *   **Cl@ve Móvil**: Requires entering DNI + Support Number, then waiting (up to 5 mins) for a push notification or scanning a QR code.
    *   **Cl@ve PIN**: Requires entering DNI + Support Number, requesting a PIN (via SMS/App), and then entering the received PIN into a second form field.
*   **Protocol Evaluation**: The current `AuthProvider.authenticate()` signature is a single `async` call. For Cl@ve, this would require:
    *   **Polling**: The method would block while polling the Playwright page for the expected redirect after out-of-band confirmation (Móvil).
    *   **Challenge/Response**: For PIN entry, the protocol needs a way to communicate a "Request for Input" back to the user (e.g., via a callback or by returning a "Pending" state).
*   **Conclusion**: The `AuthProvider` protocol is "capable" of supporting Cl@ve via blocking `await` calls, but a more robust implementation for Kent would benefit from an interactive "Resume" pattern or a callback injection for PINs.

## Pending Issue Domain

The following items are identified for future work cycles:

1.  **Configurable Resilience**: Expose `AEAT_AUTH_TIMEOUT_MS` and implement a provider-aware retry strategy in `AeatAuthenticator`.
2.  **Proactive Health Gate**: Update `WorkflowEngine` or `AeatAuthenticator` to enforce `CertificatePreExpiryError` gates during the `authenticate` flow.
3.  **Cl@ve Implementation**:
    *   Implement `ClaveMovilAuthProvider` using a "Wait for Redirect" strategy.
    *   Extend `AuthProvider` or add an `InteractiveAuthProvider` subclass to support PIN entry challenges.
4.  **Harden icacls**: Consider raising a hard error if `icacls` fails on Windows when `AEAT_STRICT_SECURITY=1` is set.
