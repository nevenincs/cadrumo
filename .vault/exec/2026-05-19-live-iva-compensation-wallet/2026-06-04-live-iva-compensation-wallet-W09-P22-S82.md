---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S82'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-26-live-iva-auth-read-acquisition-adr]]'
  - '[[2026-05-26-live-iva-remote-evidence-reconciliation-adr]]'
---

# Live Read-Only IVA Remote-State Verification

Scope: `src/aeat/application/live`, `src/aeat/adapters/outbound/aeat/sede`, `src/aeat/entrypoints/cli`, `.vault/audit`, `.vault/exec`.

## Description

- Ran the read-only IVA remote-state capture and identified that a successful capture can reuse an existing persisted Clave session without producing a fresh phone prompt.
- Cleared only the persisted Clave session for the active profile, leaving profile data and remote IVA evidence intact.
- Ran isolated fresh Clave auth through `config auth login --provider clave_movil --fresh --reset-lock`.
- Recorded the operator testimonial that the Clave phone request was seen, answered, and approved.
- Ran read-only `capture-remote-state` immediately after the fresh login so the capture consumed that newly authenticated session.
- Verified backend reload using redacted aggregate counts and decision status only.
- Checked that no `config auth login` or `capture-remote-state` process remained after the run.

## Outcome

Live gates passed:

- Fresh Clave login returned `authenticated=True`, `fresh=True`, and `reused_persisted_session=False`.
- Read-only remote-state capture returned `auth_status=succeeded`, `auth_outcome=authenticated`, `auth_provider_kind=clave_movil`, and `auth_reused_persisted_session=True`.
- Filed-history and wallet/cartera surfaces both succeeded.
- Backend reload reported 12 IVA compensation history rows, 8 carry-forward lots, 2 authority decisions, 12 wallet observations, and 25 acquisition manifests.
- The visible 2026 1T and 2T authority decisions select `aeat_wallet`, carry `wallet_only` divergence, and are not blocked or stale.

## Notes

No live filing, payment, confirmation, represented-taxpayer selection, or AEAT write path was executed.

Two earlier attempts are retained as honest failure evidence: one read-only capture failed before live access because `AEAT_LIVE_TESTS_ENABLED` was not the exact literal `1`, and one forced fresh capture failed with `operator_timeout`. The conclusive successful sequence was auth-first: clear persisted session, fresh Clave login with operator approval, then read-only capture via the newly persisted session.
