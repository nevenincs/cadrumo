---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S121'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# re-run Pere pensioner-landlord and Marc autonomo to confirm tarifa applied 130-to-100 projection discoverable IVA-wallet queryable Pere 1250 EUR gestor figure reconciles

## Scope

- `.vault/audit/`

## Description

- Create fresh Pere and Marc personas in separate file-backed encrypted local stores through `uv run aeat`.
- Calculate Pere's 2025 Modelo 100 with pension and capital-inmobiliario casillas, retaining no economic-activity category or estimation-regime input.
- Inspect Marc's Modelo 130 missing bindings, calculate its 2026/2T draft from the empty local ledger and explicit prior-filing zeros, and query the 2026 IVA-wallet balance.
- Invoke the public 2026 M130-to-M100 projection and the M100 work-creation route to retain their registry-bound refusal evidence.
- Record the persona evidence and its unresolved boundary in the rolling continuity audit.

## Outcome

Pere's fresh Catalunya pensioner-landlord profile reported `activities.description <unset>`. Modelo 100 work unit `325ea7b76e375a8612fdc49ded897ad60dcf472b67b7173008129831be48060b` calculated successfully (exit 0) into draft `715b358cf863939c39941136cc8e5a676c68a54d33c3ec474ef0d40c04f0fe14`. The real result retained positive tariff casillas `0545=4910.25` and `0546=5132.50` (`0670=10042.75`), and its binding values did not include `renta-2025-modelo-100-estimacion-directa-es-normal`. This is the intended no-business route: no activity fact, estimation regime, or invented activity amount was supplied.

Marc's 2026/2T Modelo 130 work unit `58900fe2c9f3c460befcf8e3222fc48dce91bf28dc5362b274aa669d466cf505` first refused missing prior-filing bindings (exit 1), then saved draft `0b14631781c04c9c06c8874d292f9961d8867450d06a15cf795d12aa7dd93e29` (exit 0) when only the three disclosed prior-filing values were set to zero. Its empty local ledger remained zero-valued; no business transaction or activity amount was invented. `aeat app modelo iva-wallet balance --as-of-year 2026` exited 0 and returned `total_balance=0`, `active_balance=0`, `expired_balance=0`, and `lot_count=0`.

The public `aeat app modelo project --year 2026 --ccaa madrid` command is discoverable and consumed Marc's calculated Modelo 130 path, but exited 1 with the explicit refusal that no registry revision covers Modelo 100 for 2026/0A. A direct 2026 Modelo 100 work creation also exited 1 because no law-determined revision exists. Consequently no live M130-to-M100 projection can be claimed for 2026. The W07.P34 brief contains the bare phrase "Pere 1250 EUR gestor figure reconciles" but identifies neither a source nor factual inputs for €1,250; neither persona produced that amount, so it remains unreconciled rather than being inserted into a calculation.

## Notes

All commands used `uv run --no-sync aeat` with separate temporary, file-backed encrypted stores and no contact with AEAT services. Expected refusal exits are retained as evidence, not treated as command failures. This execution record does not close S121 or the plan: the live 2026 M100 registry gap and unsupported €1,250 claim require W07.P34 consolidation and plan expansion.
