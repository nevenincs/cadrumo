---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S32'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# OWNER-GATED DEFERRED: remove the write-only standalone salt artefact and shrink the torn-install detection tuple after owner review per the no-legacy-compatibility key-management caution

## Scope

- `src/aeat/adapters/persistence/storage/master_key/_master_key.py`

## Description


- Prove the salt file is non-load-bearing: KEK derivation reads
  `master.kdf.salt_b64`; the standalone `salt` file is only ever
  existence-checked (torn-install + readiness), never byte-read for derivation
  (comprehensive grep: zero byte-reads).
- Obtain explicit owner authorisation (the `no-legacy` key-management caution
  mandates owner sign-off for master-key-store changes).
- Stop writing the `salt` file in mint + recovery; drop the `_salt_path` property.
- Shrink the torn-install artefact tuple and keychain-fallback readiness checks
  to `(master.key, master.kdf)`.
- Update docstrings to the two-artefact model.
- Rework the torn-state tests to the two-artefact model; assert the salt file is
  absent; fix the 0o600 / no-install loops and the custody lifecycle assert.

## Outcome

STEP COMPLETE (owner-authorised). The write-only standalone `salt` artefact is
removed from the file-fallback master-key store. The per-store random salt is
carried solely inside `master.kdf` (`salt_b64`), which is what KEK derivation has
always read; the standalone file was informational and never load-bearing.

Safety analysis (discharging the owner-gate): derivation is **untouched** — no
code path reads the standalone salt file's bytes, so removing it cannot strand
encrypted data. The only behavioural change is torn-install detection: a store
with `master.key` + `master.kdf` but no `salt` was previously refused as torn and
is now correctly treated as **complete** (it carries everything derivation needs).
Pre-beta / no-legacy means no migration — an old store with a leftover `salt`
file unwraps fine (the file is ignored).

Gates: master-key suite 209 pass; full storage suite + CLI custody lifecycle 847
pass. Lint clean.

## Notes


This was the one campaign step the `no-legacy` key-management caution placed
behind an explicit owner gate (a wrong deletion in the master-key store is
unrecoverable). The gate was discharged by (1) a comprehensive proof that the
artefact is non-load-bearing and (2) explicit owner authorisation, not by
overriding the gate under completion pressure. The reworked torn-state tests are
stronger coverage of the new two-artefact contract (`master.key`-only and
`master.kdf`-only are both torn; the former `master.key`+`master.kdf` "torn" case
is now complete and was removed, not weakened).
