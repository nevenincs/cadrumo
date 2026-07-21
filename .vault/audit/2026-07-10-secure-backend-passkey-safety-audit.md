---
tags:
  - '#audit'
  - '#secure-backend-passkey-safety'
date: '2026-07-10'
modified: '2026-07-13'
related:
  - "[[2026-05-14-secure-backend-passkey-custody-adr]]"
  - "[[2026-05-22-secure-storage-production-hardening-architecture-adr]]"
---

# `secure-backend-passkey-safety` audit: `passkey plan HEAD reconciliation: superseded by production-hardening`

## Scope

Verify-close reconciliation of the accepted 2026-05-14 secure-backend-passkey-custody
ADR and its execution plan against HEAD. The plan carries 52 steps across 11 phases with
24 checked. The reconcile brief flagged the checkboxes as stale relative to more-advanced
code. This audit records the true per-step state at HEAD, honestly, without fabrication.
It is a reconciliation only; no crypto or storage code was authored.

## Findings

### passkey-plan-superseded-by-production-hardening | high | the 2026-05-14 passkey plan was superseded as an execution vehicle by the 2026-05-22 production-hardening refactor

The passkey ADR's core custody decisions are largely realized at HEAD, but NOT through
this plan's own P05-P11 steps. They landed through the successor
`secure-storage-production-hardening` architecture (accepted 2026-05-22), whose ADR
explicitly enrolls the passkey custody ADR chain into a single production contract
("explicit operator enrollment through profile creation, passphrase-backed custody,
recovery, profile switch session opening, profile logout teardown, and rotation
semantics"). The successor took a profile-centric verb model and a different file layout,
so this plan's step-level file and verb names are stale. The foundation phases the plan
DID execute (P01-P03) are solid: the `bucket` and `master_key` module suites are green
(286 passed, -n0). `BucketSession` is production-wired (the D10 engine-lifecycle bind),
idle-timeout is enforced through the bucket manifest, Argon2id KEK derivation and
AES-256-GCM DEK wrap exist as their own modules, and silent auto-mint is gone from the
setup service.

### passkey-custody-verbs-landed-under-different-modules | medium | rekey/recover/show-recovery/verify-recovery/switch/lock exist, but as secret-store custody verbs, not the planned per-verb files

ADR decision 7's canonical verb set is satisfied at HEAD, but the verbs live in
`src/aeat/entrypoints/cli/_config/_custody_secret.py` (`config rekey`, `config recover
--recovery-key`, `config show-recovery`, `config verify-recovery`, `config lock`) and
`_custody.py` (`config switch`), driven by a `secret_store` / `user_profile` application
abstraction (`rekey_secret_store`, `recover_secret_store`, `mint_recovery_code`,
`verify_recovery_code`, `logout_active_profile`). The plan named `_unlock.py`, `_rekey.py`,
`_recovery_view.py`, `_recover.py`, `_switch.py` — none of which exist. The data-loss copy
mandate (ADR decision 8) is honoured on the custody surface via
`tr("cli.config.custody.data_loss_warning")`, though not through the P06 wizard screens the
plan specified.

### passkey-plan-verbs-not-built-as-specified | medium | several planned P05-P11 steps have no HEAD equivalent under any name

`config unlock` (P05.S02) does not exist as a standalone verb; `config switch` subsumes
the select-and-open path, and only `config lock` landed of the S02 pair. There is no
`config list-buckets` (P05.S06 — the successor exposes `config profile list`), no `config
delete-bucket` (P05.S08 — `config profile delete` plus the bucket-archive subgroup), no
`config export-bucket` / `config import-bucket` (P05.S09 — `config profile bundle`), and no
`config set idle-lock-minutes` (P05.S10 — idle-lock is manifest/settings-driven, not an
operator verb). The P06 enrollment-wizard rewrite (passphrase double-confirm, recovery-code
confirm-by-retype, data-loss acknowledgement screens) is not present as specified; enrollment
is profile-creation-based and recovery is minted post-hoc via `config show-recovery`. The
P08 terminology denylist tests (`test_no_storage_vault_identifier.py`,
`test_error_message_terminology.py`, `test_locale_storage_terminology.py`), the P09
legacy-layout refusal gate (`LegacyLayoutDetectedError` in `application/setup`), the P10 e2e
test files at the planned `_config/tests/test_e2e_*.py` paths, and the P11 docs
(`docs/cli/config.md`, `docs/concepts/lock-unlock-recovery.md`, the README data-loss banner,
the vault reference doc) do not exist at HEAD. P09 is additionally moot under the
`no-legacy-compatibility` rule (unreleased pre-beta, no released data to refuse).

### passkey-plan-p04-p05s01-checked-without-exec-records | low | six already-checked steps carry no execution record

`vaultspec-core status` reports P04.S01-S05 and P05.S01 as checked but with "no record".
Their planned files are also stale (`workflow/_active_bucket.py`, `_bucket_pointer.py`, and
the Google `_profile_binding.py`, which was renamed to `_active_profile.py` per the
`binding-names-reserved-for-registry-input` rule). This is pre-existing checkbox/exec-record
drift under `plan-closure-requires-exec-records`, inherited from the superseded execution,
not new to this reconcile.

## Recommendations

Mark the `2026-05-14-secure-backend-passkey-bucket-plan` SUPERSEDED by the
`2026-05-22-secure-storage-production-hardening-refactor-plan`, which is where the custody
surface actually landed and where its residual work should be tracked and closed. Do not
piecemeal-flip the passkey plan's remaining boxes: the four verbs that are genuinely
satisfied at HEAD (rekey, recover, show-recovery/verify-recovery, switch) were built by the
successor, and closing them under this plan with per-step exec records would misrepresent a
superseded plan as incrementally self-executing while the majority of its steps
(list/delete/export/import/set verbs, wizard screens, terminology tests, legacy gate, e2e
files, docs) have no HEAD equivalent. The passkey ADR itself stays accepted and honoured —
its decisions live on in the production-hardening architecture. FIDO2-hardware passkey
custody remains out of scope (operator declined the hardware). No autonomous crypto/key
action is warranted; any residual custody hardening belongs to the successor plan under its
own review.
