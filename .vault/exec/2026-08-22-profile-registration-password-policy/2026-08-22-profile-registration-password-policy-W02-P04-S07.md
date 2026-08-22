---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:0a4f8afaca760173c73dcd4c664d068a301f0930733679cf910885b3fdf0473e'
step_id: 'S07'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---

# Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then map canonical prospective refusals through registration and rotation before mutation, delete stale application policy paths, and prove exact no-mutation behavior

## Scope

- `src/cadrumo/application/user_profile`

## Description

- Ground registration and rotation behavior plus the governing credential ADR through semantic discovery and exact symbol confirmation.
- Map every canonical prospective-password refusal through one secret-free typed application payload with stable translation keys and bounded numeric context.
- Validate registration before identity generation and KDF work, and validate rotation before root resolution, transaction locking, unwrap, record re-heading, and envelope publication.
- Remove the stale minimum-only mapping and the registration-key reuse in rotation without aliases or compatibility branches.
- Export the typed refusal payload through the application facade.
- Prove refusal boundaries and exact accepted Unicode behavior against real custody and storage.
- Freeze refusal presentation context structurally, pin its exact finite message and context contract, and bite every preflight ordering seam with fail-if-called collaborators.
- Apply Ruff formatting only to the S07-owned production and test files.

## Outcome

Registration and rotation now preserve the canonical refusal reason and safe scalar or byte measurements on their existing typed error families. Every invalid prospective credential is rejected before cryptographic, transactional, session, journal, record, inventory, or envelope mutation. Both capabilities cover 14 and 257 scalars, 1,025 bytes, both surrogate halves, the accepted 15/256/1,024 boundaries, and byte-exact composed/decomposed credentials.

Review remediation removes the payload's mutable context container while preserving the established mapping read surface and error-context copying convention. Dedicated ordering bites prove registration refuses before identity, randomness, custody, and KDF work, while rotation refuses before root resolution, locking, loading, unwrap, re-heading, and publication. The durable whole-storage snapshot proofs remain independent.

Focused Ruff check and format-check pass over all six owned files. The real integration lane passes all 37 registration and rotation tests in 44.92 seconds.

## Notes

While the focused integration lane was running, shared-worktree commit `cee3240301` consumed the production and test changes together with peer-owned files. No peer work was reverted or restaged. The implementation evidence therefore spans that commit and the narrow S07 facade-and-record commit. Locale catalogs and error-code registry declarations remain assigned to S10; this Step establishes stable application message keys only.

The preflight bite tests replace only the named in-process application collaborators with fail-if-called sentinels. They do not replace custody behavior in any success or persistence test; all existing real-storage and real-KDF proofs continue to run unchanged.
