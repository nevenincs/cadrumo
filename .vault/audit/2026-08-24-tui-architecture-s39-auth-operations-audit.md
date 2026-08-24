---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:eaa5dcf8524a87194911530a28a8701e01b7fd95b301ff0635dc174f2af4b5be'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `s39 auth operations`

## Scope

Independent review of S39's auth operation definitions, real supervisor/custody test coverage, passphrase custody boundary, and the subsequent request-storage semantic audit.

## Findings

- [MEDIUM â€” resolved] The four non-secret registrations originally had no real-supervisor execution proof. Resolution added custody-backed supervisor coverage for provider configuration, AEAT session acquisition refusal before outbound access, logout, and reset. The proof records terminal condition, exact effect, result reference, active-profile binding, and the distinct behavior that logout preserves configuration while reset clears it.
- [MEDIUM â€” resolved] Secret-submission validation was overconstrained to credential-free request storage, exposing active-custody rotation metadata in the journal. Resolution permits the generic requirement broker with either storage policy, retains the recorded/interrupt/pre-entry-none invariants, changes rotation to secure-reference storage, and leaves credential-free storage only for pre-DEK profile login.

## Recommendations

No remaining critical, high, or medium finding. Preserve the generic secure-reference secret-submission regression when evolving the operation registry.
