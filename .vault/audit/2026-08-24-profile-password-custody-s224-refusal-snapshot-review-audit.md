---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:9464078feaab8e3386591248d3e8695221c4e080dc7e6c323989773167b764e0'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# `profile-password-custody` audit: `S224 refusal snapshot review`

## Scope

Independent re-review of the S224 refusal-snapshot witness and its related
session-lifecycle repair. It covers the shared generated snapshot source for
the portable/POSIX and native Windows HANDLE harnesses, the host-side
`_storage_snapshot`, and the real receipt lifecycle that the strengthened
witness exposed.

## Findings

### s224-lock-artifact-witness | resolved | Lock artifacts must remain visible

The earlier S224 record incorrectly treated `.lock` exclusion as the resolving
predicate. That would hide the exact durable session-lock churn the refusal
witness exists to detect. Corrective commit `5e51632799` removes both suffix
exclusions: the two generated harnesses share one logs-only predicate and the
host helper has the same logs-only policy. Session, receipt, retirement, root,
and lock files are all compared byte-for-byte; no test or production path
unlinks a lock leaf.

### s224-real-lifecycle-root-cause | resolved | Refusal had materialised a session lock

The retained lock witness exposed a real production mutation: an absent
`resume_profile_session` acquired the per-profile session lock, creating an
empty `.session.v2.json.lock` before a root-secret refusal. The repair routes
all current session lifecycle operations (mint, resume, delete, idle renewal)
through the existing re-entrant custody root lock before the per-profile leaf.
For established profiles, the absent receipt/journal observation is therefore
race-free against cooperating writers and does not materialise a session lock.
A raw unprovisioned root remains explicit bootstrap work, not an observational
refusal.

### s224-validation-and-race-review | resolved | Invalid calls and cross-process ordering are witnessed

Commit `a26f609f2e` validates profile identity, custody generation, epoch, DEK
length, mint windows, UTC instants, renewal ownership, and renewal deadline
before it opens the root lock. Cold-root regressions prove malformed mint and
renewal input creates no custody coordination artifact. The independent child
resume versus real parent mint regression establishes cross-process root-lock
linearization: on a usable keychain the child resumes the newly minted record;
on a keychain-less host it proves blocking/serialization and an honest
refusal only, not successful visibility.

## Evidence

- Global no-skip: `23 passed, 2 failed` before; final `25 passed`.
- Documented-command conformance: `347 passed, 2 failed` before; final `349 passed`.
- Locales: 30 incomplete catalogues and 253 untranslated/fuzzy entries in each
  of es, ca, and hu before; final localization gate `10 passed`.
- Receipt/race/validation focus: `9 passed`; Ruff and targeted `ty` clean.
- Authoritative machine-secret integration matrix after the final validation
  change: `70 passed in 497.07s`.
- Independent review: PASS. It found no lifecycle writer bypass, inverse
  root-to-leaf ordering, new redeclaration, lock exclusion, or remaining S224
  blocker.

## Final disposition

Approve S224's corrected witness and the related session lifecycle repair.
The evidence retains lock files rather than excluding them. The wider
profile-setup page materialization command is currently blocked before
sequence evaluation by independently owned Modelo 303/322 registry semantic
conflicts; that external registry residue is recorded in the S223 closure
record and is not presented as an S224 pass.
