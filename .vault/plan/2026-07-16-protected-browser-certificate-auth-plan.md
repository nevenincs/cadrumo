---
tags:
  - '#plan'
  - '#protected-browser-certificate-auth'
date: '2026-07-16'
modified: '2026-07-24'
tier: L2
related:
  - '[[2026-07-16-protected-browser-certificate-auth-adr]]'
  - '[[2026-07-16-protected-browser-certificate-auth-research]]'
  - '[[2026-07-16-protected-browser-certificate-auth-audit]]'
---

# `protected-browser-certificate-auth` plan

### Phase `P01` - Remove residual parallel authorities

Make the live code and accepted decision corpus expose only encrypted certificate-bound protected-browser state.

Remove the final plaintext, lifecycle, coverage, and decision-corpus gaps
without restoring any retired certificate-auth compatibility surface.

- [x] `P01.S01` - Delete implicit plaintext profile storage-state consumption from fresh provider sessions and make every persistence source explicit; `src/cadrumo/adapters/outbound/aeat/browser/session.py; src/cadrumo/adapters/outbound/aeat/auth/`.
- [x] `P01.S02` - Reconcile every still-accepted auth decision with the protected-browser authority and remove retired handshake marker and configurable-target clauses; `.vault/adr/2026-04-17-session-persistence-adr.md; .vault/adr/2026-04-17-aeat-access-gate-adr.md; .vault/adr/2026-04-18-auth-provider-abstraction-adr.md; .vault/adr/2026-04-18-auth-protocol-adr.md`.
- [x] `P01.S03` - Correct maintainer contracts that still describe marker evidence or implicit browser-factory construction; `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py`.

### Phase `P02` - Harden owned browser lifecycle

Close every provider-owned context and browser deterministically across failures and concurrent close calls.

- [x] `P02.S04` - Close Clave contexts and browsers when fresh-session persistence fails before ownership transfer; `src/cadrumo/adapters/outbound/aeat/auth/_clave_movil.py; src/cadrumo/adapters/outbound/aeat/auth/_clave_permanente.py`.
- [x] `P02.S05` - Make certificate context teardown bounded retryable and primary-exception preserving; `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py; src/cadrumo/adapters/outbound/aeat/auth/_browser_lifecycle.py`.
- [x] `P02.S06` - Serialize concurrent provider closure so the drain barrier cannot tear down newly admitted work; `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py; src/cadrumo/adapters/outbound/aeat/auth/_clave_movil.py; src/cadrumo/adapters/outbound/aeat/auth/_clave_permanente.py`.

### Phase `P03` - Prove and close the hard cut

Replace synthetic proof coverage with the strongest credential-free real behavior available, retain the external live oracle, and close only after repository-wide gates.

- [x] `P03.S07` - Replace synthetic decisive proof and lifecycle coverage with credential-free real browser and process behavior while retaining the external live protected oracle; `src/cadrumo/adapters/outbound/aeat/auth/tests; src/cadrumo/adapters/outbound/aeat/browser/tests`.
- [x] `P03.S08` - Run repository-wide quality Vault documentation packaging and CI-equivalent gates and resolve the formal audit; `.vault/audit/2026-07-16-protected-browser-certificate-auth-audit.md; repository`.

## Description

Execute the accepted protected-browser certificate-auth decision and resolve
the formal reconciliation audit. The implementation retains one exact
Playwright protected-resource proof, typed certificate credentials, encrypted
session persistence, and provider abstraction while deleting residual
plaintext state tolerance and making context and browser ownership reliable
under failure and concurrency.

## Steps

## Parallelization

Phase P01 decision-corpus work can run alongside its storage-authority and
maintainer-contract code changes. Phase P02 lifecycle fixes can be split by
certificate and Cl@ve ownership, but the concurrent-close contract must be
shared across all three providers. Phase P03 starts only after P01 and P02
settle so its real-behavior tests and repository gates exercise the final
architecture.

## Verification

The feature is complete only when semantic and exact searches find no active
handshake, marker, backend-selection, configurable-target, implicit plaintext
storage-state, or compatibility authority; every accepted auth decision agrees
with the protected-browser ADR; real Playwright process and lifecycle tests
pass without fakes, mocks, stubs, patches, skips, or xfails; the external live
oracle remains exact and fail-closed; the full pytest, style, format, type,
import, registry, documentation, Vault, and GitHub CI gates pass; and every
Step has its CLI-checked state and execution record.
