---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S08,S10,S26'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-live-auth-blocker-audit]]'
---

# W02.P03.S08 / W02.P04.S10 / W03.P06.S26 isolated live auth timeout

## Scope

Ran the authenticated read-only live runner against a fresh isolated profile,
secret store, blob store, and local storage root, then stopped it after Cl@ve
authentication timed out and downstream live reads could not acquire a session.

## Description

- Updated the live runner to use `pull` acquisition verbs only and removed the
  live `pull-all` refusal probe from the authenticated command sequence.
- Scoped `AEAT_LOCAL_STORAGE_ROOT`, `AEAT_SECRET_STORE_DIR`, and
  `AEAT_BLOB_STORE_DIR` under one isolated live root so a newly generated
  process-local passphrase minted a new master key.
- Created profile `live-auth-20260613-isolated` and configured Cl@ve Movil
  against the redacted configured identity.
- Attempted fresh visible non-QR Cl@ve login and then censo pull.
- Stopped the runner before allowing the remaining filed, expedientes,
  notifications, justificante, and calendar commands to repeat auth timeouts.

## Outcome

Local secure-storage and profile creation are operational in a fresh isolated
root. Cl@ve provider configuration also succeeded and identity alignment was
reported as matching. No authenticated AEAT session was acquired, so no
positive Modelo 036/censo, filed-history, expediente, notification,
justificante, or live-backed calendar evidence is claimed.

The live blocker is external/operator-mediated Cl@ve completion. The AEAT page
showed non-QR Cl@ve confirmation flows with verification codes in the visible
browser, but the CLI timed out waiting for AEAT to reach the post-auth landing
page.

## Verification

- `uv run aeat config profile create live-auth-20260613-isolated --quiet --accept-defaults --entity-type natural_person --tax-id <redacted> --name Live --surnames Operator --irpf-income-categories actividad_economica --activity actividad_economica --output-language en`
  - result: exited 0; profile created and activated.
- `uv run aeat config auth configure --provider clave_movil`
  - result: exited 0; provider configured, profile tax id present, Cl@ve
    identity present, identity alignment matches.
- `uv run aeat config auth status --provider clave_movil`
  - result before login: exited 0; configured true, authenticated false,
    active profile ready.
- `uv run aeat config auth login --provider clave_movil --fresh --reset-lock`
  - result: exited 3; `auth_completion_timeout`; diagnostic
    `20260613T110618Z`; no persisted authenticated session.
- `uv run aeat config auth status --provider clave_movil`
  - result after login: exited 0; configured true, authenticated false.
- `uv run aeat config profile censo pull`
  - result: reached auth preflight, then exited 3 with
    `auth_completion_timeout`; diagnostic `20260613T110838Z`; no censo
    snapshot captured.
- `uv run aeat config profile censo compare`
  - result: exited 2; refused because no censo snapshot had been captured.
- Local isolated evidence:
  - active profile pointer exists under the isolated root.
  - profile bucket database exists under the isolated root.
  - encrypted `master.key` exists under the isolated root's `secrets`
    directory.
  - token directory exists under the isolated root.

## Notes

The runner was stopped after `app live filed list --from-year 2025 --to-year
2026` entered another auth preflight. The stopped run did not complete filed
history, expedientes, notifications, justificante, or calendar commands.
