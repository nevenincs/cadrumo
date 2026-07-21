---
tags:
  - '#audit'
  - '#secure-backend-passkey-safety'
date: '2026-07-10'
modified: '2026-07-17'
related:
  - "[[2026-05-14-secure-backend-passkey-custody-adr]]"
  - "[[2026-05-22-secure-storage-production-hardening-architecture-adr]]"
---

# `secure-backend-passkey-safety` audit: `passkey plan HEAD reconciliation: superseded by production-hardening`

## Scope

Verify-close reconciliation of the accepted 2026-05-14 secure-backend-passkey-custody
ADR and its execution plan against HEAD. The historical plan carried 52 steps across 11
phases with 24 checked, but only 16 retained execution records. The reconciliation retains
those 16 evidence-backed checks and retires every other structural row; none was checked
from code inspection or successor-plan work. The reconcile brief flagged the old checkboxes
as stale relative to more-advanced code. This audit records the true per-step state at HEAD,
honestly, without fabrication. It is a reconciliation only; no crypto or storage code was
authored.

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

### successor-unlock-claim-diverges-from-code | medium | the successor record claims `config unlock`, but HEAD exposes `config switch`

The successor production-hardening plan and a related rollout audit describe `aeat config
unlock` as a first-class custody command. HEAD registers `lock`, `rekey`, `recover`,
`show-recovery`, and `verify-recovery` in `_custody_secret.py`, and registers `switch` in
`_custody.py`; there is no `unlock` command. `switch` remains the select-and-open lifecycle
path. This is successor-plan and successor-audit drift, not a reason to reopen or credit
the retired P05.S25 row. The successor must reconcile its own wording to the live CLI.

### passkey-plan-checkbox-and-exec-drift | low | eight historical checks lacked retained execution records

The historical plan carried 24 checked rows but only 16 retained execution records. In
addition to P04.S01-S05 and P05.S01, P03.S06 and P03.S07 had no per-step execution record.
The P03 implementations are visible at HEAD, but code inspection is not execution evidence.
The P04/P05 planned files are also stale (`workflow/_active_bucket.py`, `_bucket_pointer.py`,
and the Google `_profile_binding.py`, which was renamed to `_active_profile.py` per the
`binding-names-reserved-for-registry-input` rule).

The current-schema reconciliation retains only the 16 evidence-backed checks, each bridged
to its historical record. The two incomplete P03 rows and all P04+ rows are retired from
the plan rather than left open: their historical identifiers remain visible in the plan's
Vaultspec retirement annotation, while this audit preserves their disposition. This preserves
the `plan-closure-requires-exec-records` rule without crediting successor-plan work to the
superseded plan.

### retirement disposition | passkey plan has no remaining execution scope

- `S17`-`S18`: visible HEAD behavior but no retained execution record for the historical
  rows; successor ownership makes retrospective completion misleading.
- `S19`-`S23`: obsolete active-bucket naming and file targets; the profile-centric successor
  architecture owns the live routing model.
- `S24`-`S33`: partly replaced by successor custody and profile commands, partly never built
  as specified; none has the planned file or verb contract.
- `S34`-`S37`: the wizard and Drive-mirror changes were not built as specified.
- `S38`-`S42`: terminology work lacks the planned scope, and the legacy-layout gate is moot
  under the unreleased no-legacy-compatibility policy.
- `S43`-`S48`: no planned end-to-end or property-test files exist; successor coverage cannot
  serve as execution evidence for this plan.
- `S49`-`S52`: none of the planned documentation or reference targets exists at the stated
  path.

All of these rows are retired, not complete or deferred. Residual production custody work
must be planned and evidenced under secure-storage-production-hardening.

## Recommendations

The `2026-05-14-secure-backend-passkey-bucket-plan` is SUPERSEDED and closed by the
`2026-05-22-secure-storage-production-hardening-refactor-plan`, where its residual custody
work is tracked and closed. Its 36 non-evidenced rows are retired rather than piecemeal
checked: the related HEAD behavior belongs to the successor and several planned targets have
no equivalent. The passkey ADR stays accepted and honoured because its decisions live on in
the production-hardening architecture. FIDO2-hardware passkey custody remains out of scope
(operator declined the hardware). No autonomous crypto/key action is warranted.
