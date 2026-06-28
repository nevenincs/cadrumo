---
tags:
  - '#audit'
  - '#iva-compensation-override-cli'
date: '2026-06-19'
modified: '2026-06-19'
related:
  - '[[2026-06-19-iva-compensation-override-cli-adr]]'
  - '[[2026-06-19-iva-compensation-override-cli-plan]]'
  - '[[2026-06-19-crossperiod-filing-deadlock-adr]]'
---

# `iva-compensation-override-cli` audit: `Adversarial review: P01 override recorder reverted (missing guard, sticky-shadow, redundant)`

## Scope

Adversarial fan-out review of the P01 implementation of the
`iva-compensation-override-cli` plan: the application-layer recorder
`record_iva_compensation_override_for_bucket` (in `_iva_wallet_seed.py`), its
`MODELO_IVA_WALLET_OVERRIDE_RECORDED` event, the facade promotion of
`IvaCompensationOverride`, and its behaviour test. The implementation was
committed prematurely against a `proposed` (unapproved) ADR. The review attacked
it from four distinct angles (filed-immutability, evidence theater,
redundancy/canonical-mechanism, test honesty); every finding below is confirmed
against the code, not the reviewer's word. The implementation commit was
**reverted** as a result.

## Findings

### F1 (CRITICAL) Missing sealed-filing guard

`record_iva_compensation_override_for_bucket` carried only a NIF check and a
negative-amount check. Its sibling `correct_iva_compensation_period_for_bucket`
in the same module carries `_sealed_modelo_303_blocker_for_period`, which refuses
to change a compensación balance that a sealed (VERIFICADO_COMPLETO / PRESENTADO /
PRESENTADO_SUPERSEDIDO) Modelo 303 revision at or after the period has already
consumed. The override recorder dropped that guard, so an operator could record
or overwrite an override for a period whose compensación a filed return already
consumed, silently changing the basis of a filed return — the exact
filed-immutability risk the `correct` guard and the ledger restore guard exist to
prevent.

### F2 (CRITICAL) Sticky override silently shadows filed evidence

The iva-wallet decision OWNS the `modelo-303-compensacion-pendiente-anteriores`
binding (ruling D3 in `_calculation_actions.py`), and
`resolve_iva_compensation_decision_for_calculation` returns a persisted decision
WITHOUT re-reconciling when one exists. A recorded `taxpayer_override` decision is
therefore sticky: every later `calculate` uses it and never re-reads filed-history
observations for the period. An operator override that contradicts a quarter that
is filed AFTER the override silently wins, with no collision detection — a
`no-silent-under-declaration` exposure. This is the pre-existing sticky-decision
defect, sharpened into a safety hazard by an operator-asserted override.

### F3 (HIGH) Provenance is theater

`IvaCompensationOverride` requires `reason` and `evidence_locator`, but both are
unvalidated free strings — never resolved against any real evidence (justificante,
attachment, wallet capture). The operator can set casilla 110 to any amount with
`reason = "x"`, `evidence_locator = "y"`. The ADR's "mandatory provenance" is
cosmetic, and the override defeats the very safety gate it claims to honor.

### F4 (HIGH) Behaviour test overclaims and is near-tautological

The test asserted only `casilla 110 == 420` (the value supplied equals the value
read back) — never the final result casilla (the claimed 525), used a synthetic
fixture rather than the originating persona scenario, and had no negative control
proving casilla 110 would be zero or blocked WITHOUT the override. The closing
report's "2T resolves to 525" and "end-to-end" claims were unverified by the test.

### F5 (MEDIUM) Redundant with the canonical late-file carry

The peer cross-period-filing-deadlock work makes `work file` succeed for a
closed/overdue prior period, creating the app_filing observation that the next
period's previous_filing binding reads — the grounded, e2e-tested carry source
(`test_e2e_ledger_m303_quarters_to_m390_annual.py`). The override is a
less-grounded input whose necessity, now that the late-file path works, is in
doubt except for the narrow "filed entirely outside the app" case the seed
already half-covers. The reviewer's stronger "two parallel mechanisms / canonical
violation" framing is tempered here: the decision is the single binding owner and
override is one of its authority inputs — but the sticky-shadow (F2) makes it
behave like a conflicting path.

### F6 (process) Premature execution

P01 was implemented and committed on a `proposed` ADR, against the vaultspec
plan-approval mandate, and shipped two CRITICAL gaps. The fan-out adversarial
review (rather than the author's self-report) is what surfaced them.

## Recommendations

- The implementation commit is reverted; the codebase is back to pre-P01 state
  (the seed/correct surface is unchanged and green).
- Do NOT re-implement the override until the ADR is reconsidered. The override, if
  retained, MUST: (1) carry the same sealed-filing guard as `correct` (F1);
  (2) refuse to overwrite — or at minimum re-reconcile / flag — when a persisted
  decision or filed-history observation for the period would be shadowed (F2);
  (3) be narrowed to the genuine "never-filed-in-app prior balance" case, since
  the canonical late-file path now covers the in-app case (F5).
- Prefer the canonical late-file carry (peer work) as the primary mechanism;
  scope the override to the residual case only, or drop it.
- Any re-implementation's test MUST assert the FINAL result and include a negative
  control, and exercise the real persona scenario, not a synthetic value passthrough
  (F4).
- Fix the sticky-decision defect (F2) at its root — `calculate` should re-reconcile
  when the underlying seed/history/observation changed — independently of the
  override question.

## Codification candidates

- **Source:** finding F1 (override dropped the sealed-filing guard its sibling
  carries). **Rule slug:** `iva-wallet-mutations-guard-sealed-filings`.
  **Rule:** Every operator verb that writes or overwrites a Modelo 303
  compensación basis (seed, correct, override, and any future sibling) MUST refuse
  when a sealed (filed) Modelo 303 revision at or after the period has already
  consumed that basis, reusing the single sealed-state guard — never ship a new
  mutation that drops it.
