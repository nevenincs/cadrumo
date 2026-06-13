---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# W04.P02.S01-S02 persona testimonial capture and task conversion

## Scope

- Steps: `W04.P02.S01`, `W04.P02.S02`
- Goal: capture bounded persona CLI outputs and convert friction into implementation tasks.

## Commands

Local help and dry-run commands were run through the official CLI entrypoint, `uv run aeat ...`, against disposable local state under `.tmp/w04-persona-cli`.

Live AEAT commands were not executed.

## Evidence

- Persona testimonials: `.vault/audit/2026-05-21-live-iva-compensation-wallet-persona-testimonials.md`
- Persona briefs: `.vault/audit/2026-05-21-live-iva-compensation-wallet-persona-briefs.md`
- Audit findings appended: `WALLET-048`, `WALLET-049`, `WALLET-050`

## Converted tasks

- `W04.F01` - Modelo readiness must incorporate ledger preflight/readiness for ledger-owned Modelo 303 bindings.
- `W04.F02` - ledger view/status should surface tax-relevant fields needed for IVA diagnostics.
- `W04.F03` - live IVA wallet CLI help/output should explicitly name the representation-gate fail-closed policy.
- `W04.F04` - CLI surfaces must expose IVA compensation carry-forward lots and authority-source decisions.
