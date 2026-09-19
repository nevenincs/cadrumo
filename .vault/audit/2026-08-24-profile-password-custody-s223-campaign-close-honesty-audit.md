---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:553f30d08fa87d066c7523874c3bfd70538c99ea67cf7131049b5b7ed17a3f49'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
  - "[[2026-08-18-profile-password-custody-campaign-close-audit]]"
  - "[[2026-08-24-profile-password-custody-fresh-context-campaign-close-audit]]"
  - "[[2026-08-24-profile-password-custody-s206-recovery-parity-review-audit]]"
  - "[[2026-08-24-profile-password-custody-s209-posix-kdf-descriptor-attestation-review-audit]]"
  - "[[2026-08-24-profile-password-custody-s220-exec-evidence-audit]]"
  - "[[2026-08-24-profile-password-custody-s219-docs-audit]]"
  - "[[2026-08-24-profile-password-custody-s222-platform-gate-audit]]"
---
# `profile-password-custody` audit: `S223 campaign-close remediation and honesty review`

## Scope

Fresh review of every finding recorded by the prior S223 close audit: the two
no-skip sites, refusal-state snapshot coverage, documented command
conformance, Spanish/Catalan/Hungarian catalogue drift, redeclaration risk,
and the honest campaign-close boundary.

## Findings

### s223-global-gates | resolved | Original no-skip, command, and locale failures are closed

The canonical no-skip gate moved from **23 passed, 2 failed** to **25 passed**
using real filesystem/platform behavior. The documented-command module moved
from **347 passed, 2 failed** to **349 passed** after the unsupported agent
sequence was retired through its owning source and profile deletion prose was
materialized correctly. The locale gate moved from nine failing language
checks to **10 passed**: each of es, ca, and hu went from 30 incomplete
catalogues and 253 untranslated/fuzzy entries to complete truthful
translations; dash violations and orphan environment-overrides catalogues were
removed without a baseline or allowlist change.

### s223-refusal-snapshot-and-lock-lifecycle | resolved | The witness caught and closed a real mutation

The snapshot now excludes only diagnostic logs and retains every lock, receipt,
retirement, and session artifact. It revealed the empty session-lock mutation
on absent resume. The final lifecycle implementation serializes mint, resume,
delete, and idle renewal through the existing re-entrant custody root lock and
then the profile leaf. Established logged-out profiles remain byte-for-byte
unchanged by the absent probe; a raw unprovisioned root is documented as
bootstrap work rather than a refusal path.

Deterministic mint and renewal validation now occurs before root-lock
provisioning. Cold-root tests cover invalid v4 identity, generation, epoch,
DEK length, windows, ownership, and UTC deadline. An independent child resume
and real parent mint prove cross-process ordering. The KeyringUnavailable
branch is deliberately limited to serialization and honest-refusal evidence;
it does not claim successful post-mint visibility on a host with no keychain.

### s223-redeclaration-audit | resolved | Canonical authorities are reused

Semantic `vaultspec-rag` searches covered anchored capsule source refusal,
platform virtual-environment launcher resolution, durable refusal snapshots,
session/receipt lifecycle, and documentation materialization/profile deletion.
The packaging test now uses canonical `venv_bin_dir`; generated Windows and
portable harnesses share one durable snapshot source; the host helper is an
irreducible runtime-boundary counterpart matching its policy. The custody root
lock is the existing canonical primitive, not a new lock authority. No true
post-remediation redeclaration remains; behaviorally different candidates were
classified as constraints or runtime-boundary counterparts.

### s223-page-materialization | medium, external | Registry integrity blocks the page-level sequence command

`python -m dev.docs.sequences check --page how-to/profile-setup` currently
fails before materializing the S223 page due to independently owned registry
conflicts: duplicate Modelo 303 deadline semantic coordinates across revisions
and Modelo 322 filing authority with unresolved `deadline_windows`. The
profile-specific command conformance gate is green, but this full page command
is not represented as green. This residue belongs to the registry closure
owners and keeps the broader campaign-close decision open.

## Evidence

- `pytest -q -n 0 dev/tests/test_no_skip_xfail.py`: **25 passed**.
- `pytest -q -n 0 -m integration ...test_documented_command_conformance.py`:
  **349 passed**.
- `pytest -q -n 0 dev/docs/tests/test_docs_localization.py`: **10 passed**.
- Receipt/race/validation focus: **9 passed**; Ruff and targeted `ty` clean.
- Final machine-secret integration: **70 passed in 497.07s**.
- Feature and full `vault check all`: clean before the final record edits;
  final feature check is rerun after these authoritative records are written.
- Fresh independent review: PASS, with no lock exclusion/deletion, writer
  bypass, inverse lock ordering, regression, or remaining S224 blocker.

## Final disposition

S223 remediation and its evidence program are complete. Do not mark the wider
campaign close as approved while the page-level registry conflict remains red.
The audit is intentionally a truthful handoff: all S223-owned failures are
closed, and the external registry blocker is named rather than hidden.

## Recommendations

Resolve the named Modelo 303/322 registry integrity findings, then rerun the page-level profile-setup sequence command before approving the wider campaign close. Separately triage the current global Vault errors and warnings under their own historical-record owners; the profile-password-custody feature check is clean.
