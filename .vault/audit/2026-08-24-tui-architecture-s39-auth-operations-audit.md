---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:407c6e78e1333281c8c2656f1f6980b7bc1f195d284d47a16cc433a8e8099819'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `s39 auth operations`

## Scope

Independent review of S39's auth operation definitions, real supervisor/custody test coverage, passphrase custody boundary, and the subsequent request-storage semantic audit.

## Findings

- [MEDIUM - resolved] The four non-secret registrations originally had no real-supervisor execution proof. Resolution added custody-backed supervisor coverage for provider configuration, AEAT session acquisition refusal before outbound access, logout, and reset. The proof records terminal condition, exact effect, result reference, active-profile binding, and the distinct behavior that logout preserves configuration while reset clears it.
- [MEDIUM - resolved] Secret-submission validation was overconstrained to credential-free request storage, exposing active-custody rotation metadata in the journal. Resolution permits the generic requirement broker with either storage policy, retains the recorded/interrupt/pre-entry-none invariants, changes rotation to secure-reference storage, and leaves credential-free storage only for pre-DEK profile login.

### s39-rereview | low | No new issue found after generic validation correction

Re-review verified that only pre-DEK profile login uses credential-free journal storage; rotation and every active-profile authority use secure references. The generic secret declaration now enforces recorded durability, interrupt reconciliation, and pre-entry none without incorrectly constraining storage class. The journal retains only opaque references for secure requests, and all six registrations have real execution or refusal coverage without monkeypatching.

## Recommendations

No remaining critical, high, or medium finding. Preserve the generic secure-reference secret-submission regression when evolving the operation registry.
