---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W04.F09'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# `live-iva-compensation-wallet` `W04.F09`

Aligned wallet safety plan wording with the accepted guarded read-query policy.

- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

The W02 safety intent no longer uses an absolute "no AEAT form" statement. It now names the prohibited submission categories: filing, payment, confirmation, represented-taxpayer data, and operator-choice form data. It also records the single accepted exception: the centrally guarded `CarteraCuotas` wallet read-query POST, after the driver proves the form action matches the configured wallet path.

The W02.P01 phase text now requires any read-query exception to be explicit in the remote-state guard and covered by parser fail-closed tests. The W04 live-wallet persona row now asks reviewers to verify no prohibited AEAT submission occurs beyond the guarded wallet read query.

## Tests

- `uv run vaultspec-core vault plan status .vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md` completed with 44 of 44 steps complete.
- `uv run vaultspec-core vault check frontmatter --feature live-iva-compensation-wallet` reported clean.
- `uv run vaultspec-core vault check links --feature live-iva-compensation-wallet` reported clean.
