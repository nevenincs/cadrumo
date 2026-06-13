---
title: "AuthProvider Ecosystem: Pending Issue Domains"
tags: ["#audit", "#cert-provider"]
date: "2026-04-18"
modified: '2026-04-18'
related: []
---

# auth-provider pending-items

This document tracks identified issue domains and pools for the `AuthProvider` ecosystem that require a new human-in-the-loop cycle. These items were discovered during the Issue #282 audit but were deferred to maintain the surgical focus of the current refactor.

## 1. Issue Domain: Code Security & OS Hardening
- **[ ] SLATED: Strict Security Mode**
  - **Capability:** Kent's credentials are proofed against local access.
  - **Task:** Implement a hard failure in `AeatAuthenticator` if Windows `icacls` or POSIX `chmod` cannot be applied when `AEAT_STRICT_SECURITY=1` is set.
  - **Context:** Current logic is "best-effort" and logs a warning on failure.

## 2. Issue Domain: Network Robustness & Resilience
- **[ ] SLATED: Configurable Auth Timeouts**
  - **Capability:** Kent can use the tool on low-bandwidth or high-latency connections.
  - **Task:** Migrate hardcoded `30,000ms` timeouts to `Settings.aeat_auth_timeout_ms`.
  - **Context:** Identified in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py` and `provider.py`.

- **[ ] SLATED: Provider-Aware Retry Strategy**
  - **Capability:** Transient network glitches don't force a full re-login.
  - **Task:** Implement an exponential backoff retry for `verify()` calls within `AeatAuthenticator`.

## 3. Issue Domain: Certificate Condition Monitoring
- **[ ] SLATED: Proactive Health Gate**
  - **Capability:** Kent is warned before his certificate expires.
  - **Task:** Update the `authenticate()` flow to check `CertificateHealth`. Raise `CertificatePreExpiryError` if within the `CRITICAL` window (default 7 days).

## 4. Issue Domain: Multi-Factor Authentication (Cl@ve)
- **[ ] SLATED: Cl@ve Móvil Provider**
  - **Capability:** Kent can login using the Cl@ve app on his phone.
  - **Task:** Implement `ClaveMovilAuthProvider`. Use a "Wait for Redirect" strategy to handle the out-of-band push notification.

- **[ ] SLATED: Interactive PIN Challenge Abstraction**
  - **Capability:** Kent can enter his Cl@ve PIN when prompted.
  - **Task:** Extend the `AuthProvider` protocol with a `on_challenge` callback or an `InteractiveAuthProvider` subclass to handle SMS/App PIN entry.

## Status Summary
| Item | Priority | Effort | Status |
| :--- | :--- | :--- | :--- |
| Strict Security Mode | P2 | S | Pending |
| Configurable Timeouts | P1 | XS | Pending |
| Proactive Health Gate | P1 | S | Pending |
| Cl@ve Móvil | P0 | M | Pending |
| Interactive PINs | P0 | L | Pending |
