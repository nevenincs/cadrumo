---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:280a47aa9c9f78857b025f00cb554b0bb98725cade7160ba48da8dfcc3f950fe'
step_id: 'S12'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---

# Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then delete repository-wide policy bloat and stale prose, reconcile docstrings, and regenerate only feature-owned API and operator documentation

## Scope

- `repository profile credential documentation surface`

## Description

- Sweep source, tests, shipped documentation, locale references, and generated API surfaces for retired profile-credential policy and compatibility paths.
- Remove the remaining password-shaped recovery exception path and give recovery representation and proof a dedicated typed custody refusal.
- Reconcile password and recovery exception docstrings with prospective representation and cryptographic proof semantics.
- Regenerate API stubs and retain only feature-owned custody and user-profile additions.
- Prove exact obsolete-symbol absence, focused recovery behavior, error-registry binding, formatting, and generated-stub state.

## Outcome

No shipped operator guide or README states the retired policy, so no user-facing documentation rewrite was required. No eight-character profile policy, removed policy symbol, alias, shim, or raw presentation diagnostic remains. Recovery no longer raises or catches `ProfileCustodyPasswordError`; the dedicated recovery refusal is exported and registry-bound. Feature-owned API stubs now expose the recovery codec and the authentication and prospective-password modules.

## Notes

Focused recovery unit tests passed 10 tests and its integration lane passed 27 tests. Error-registry tests passed 23 tests plus 7 enforcement tests. Ruff lint and format checks pass on the owned surface. The API generator was run in apply, check, and audit modes; after retaining only feature-owned deltas it reports unrelated baseline drift in operator-surface and source-connectivity modules. The broad exception-hygiene scan is also blocked by unrelated concurrent `ContentDigest` facade drift. These baselines belong to other active work and were not consumed.

Review remediation maps wrong and malformed recovery-artifact secrets to the existing localized, context-free authentication refusal at the application proof boundary. The mapper is credential-neutral and every proof operation is explicit; no compatibility alias remains. A real Spanish renderer regression excludes adapter English, the translation key, `INTERNAL`, traceback, and the candidate, while malformed input proves no publication. Mapping tests pass 27 cases and recovery integration passes 22 cases; Ruff lint and format checks remain clean.

The final presentation-matrix bite makes both hostile candidates independently assert the exact Spanish envelope and rendered message plus a complete path-kind-byte storage snapshot. No raw surrogate is emitted in test identifiers or diagnostics. Recovery integration remains 22 passing cases and mapping remains 27 passing cases.
