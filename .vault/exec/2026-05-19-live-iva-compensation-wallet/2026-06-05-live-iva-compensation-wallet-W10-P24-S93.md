---
tags: ['#exec', '#live-iva-compensation-wallet']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S93'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---


# W10.P24.S93 live IVA evidence retry

Scope: Wave W10, Phase P24, Step S93.

## Description

- Retry read-only live IVA remote-state acquisition after auth/process cleanup hardening.
- Verify Cl@ve persisted-session reuse and no stale live browser processes.
- Acquire the requested 2022-2026 evidence through bounded per-year slices after the one-shot full-range command exceeded the CLI watchdog.
- Reload profile-local secure IVA state without contacting AEAT.

## Outcome

The operator approved Cl@ve auth, and the persisted session changed from expired to not expired. The one-shot 2022-2026 live command still failed: it timed out at the 240000 ms CLI watchdog while the active progress surface was `filed_history`.

The live read surfaces did succeed when bounded by year. Read-only `capture-remote-state` completed for 2026, 2025, 2024, 2023, and 2022 with `auth_reused_persisted_session=True`, filed-history success, wallet/cartera success, and clean post-run process inventories. The per-year filed-history counts were zero for 2026 and 2025, and four each for 2024, 2023, and 2022.

Profile-local secure reload, without live AEAT contact, returned 12 IVA history rows, 8 carry-forward lots, and 2 wallet authority decisions. This closes S93 for live evidence acquisition. The full-range one-shot timeout remains open under S100.

No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## Notes

The live evidence was recorded only as aggregate counts and outcome shape. Private taxpayer amounts from local CLI reload were not copied into this record.
