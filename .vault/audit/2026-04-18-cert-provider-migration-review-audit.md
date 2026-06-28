---
tags:
  - '#audit'
  - '#cert-provider'
date: '2026-04-18'
modified: '2026-04-18'
related:
  - '[[2026-04-18-cert-provider-migration-plan]]'
  - '[[2026-04-18-cert-provider-migration-adr]]'
  - '[[2026-04-18-cert-provider-migration-research]]'
---

# cert-provider Code Review

AUTH-001 | HIGH | CertificateAuthProvider methods are not implemented
CertificateAuthProvider.authenticate() and verify() raise NotImplementedError. The extraction of certificate logic from AeatAuthenticator into CertificateAuthProvider (Step 3 of the Plan) was not completed, leaving it as a hollow shell.

AUTH-002 | HIGH | AeatAuthenticator remains tightly coupled to certificates
AeatAuthenticator was not refactored to use the generic AuthProvider protocol (Step 4 of the Plan). It still directly imports and hardcodes PKCS#12 logic, load_certificate(), and CertificateSessionDetail. This violates the ADR's goal to decouple certificate authentication from core session management.
$content
