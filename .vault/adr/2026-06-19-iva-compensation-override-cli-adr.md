---
tags:
  - '#adr'
  - '#iva-compensation-override-cli'
date: '2026-06-19'
modified: '2026-06-19'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
  - '[[2026-05-19-iva-compensation-chain-audit-research]]'
  - '[[2026-06-19-crossperiod-filing-deadlock-adr]]'
---

# `iva-compensation-override-cli` adr: `Operator-facing IVA-wallet override verb for cross-period compensación carry` | (**status:** `proposed`)

## Problem Statement

The Modelo 303 cross-period IVA compensación carry (a quarter's "cuota a compensar"
flowing into the next quarter's casilla 110, "cuotas a compensar de periodos
anteriores") has a complete and correctly-wired data path but **no reachable
operator path** when the only available evidence is local.

The reconciliation safety model in `domain/iva_compensation/_reconciliation.py`
(`_missing_wallet_decision`) deliberately refuses to auto-apply a prior-balance
carry when there is no live AEAT wallet observation: a local recurrence or a
seeded balance is classed as "lower-confidence fallback evidence" and the
decision is returned `blocked=True` with divergence `wallet_missing` /
`filed_history_only`, whose reason states it "requires explicit taxpayer override
before automatic output". That block is correct — it upholds the
`aeat-safety-legal-gates` and `no-silent-under-declaration` disciplines (never
silently file a compensación the app cannot corroborate against AEAT).

The gap is that the override the block demands has **no operator-facing surface**.
The `iva-wallet` CLI group exposes only `balance`, `seed`, and `correct`
(`entrypoints/cli/_modelo_iva_wallet_cli.py`). A taxpayer who has seeded a prior
balance and then runs `work calculate` hits a blocked calculation (until very
recently surfaced as an opaque error; the `%{divergence}`/`%{reason}` placeholder
leak in that message was fixed alongside this ADR) with no documented way to
proceed. The end-to-end two-quarter compensación chain is therefore
operator-incompletable for the local-only flow.

A persona audit on the `chore/eliminate-shims` branch (persona `Pablo Serrano`,
Modelo 303 1T→2T 2024) reproduced this: 1T correctly generates 420 "a compensar"
and the wallet balance reads 420, but 2T resolves to 945 instead of 525 — the 420
never reaches casilla 110 — and no CLI verb can record the override that would
release it.

A secondary, related defect: `resolve_iva_compensation_decision_for_calculation`
returns a *persisted* decision without re-reconciling, so a `first_period_zero`
decision recorded by an early calculate is sticky and shadows a later seed.

## Considerations

The override machinery already exists end to end; only the recording surface is
absent:

- The domain carries an `IvaCompensationOverride` value (fields: `amount` ≥ 0,
  `reason` 1–1024 chars, `evidence_locator` 1–1024 chars, `recorded_at`). It is
  the structured, provenance-bearing taxpayer assertion the parent ADR
  anticipated.
- `reconcile_iva_compensation_wallet` already routes an override first:
  `_override_reconciliation_decision` produces a NON-blocking decision with
  `selected_authority = "taxpayer_override"`, `selected_amount = override.amount`,
  `divergence = "override"`, and `reason = override.reason`.
- The resulting `IvaCompensationReconciliationDecision` is persisted by
  `IvaWalletDecisionRepository.save_decision` keyed by period, and the calculate
  path's `apply_iva_compensation_decision_binding` reads that persisted decision
  and writes the selected amount onto casilla 110.
- The existing `seed` / `correct` verbs are the structural template for a new
  recording verb: typer command under the `iva-wallet` group, `--filing-year`,
  `--period`, `--amount`, a mandatory `--confirm` acknowledgement, locale-keyed
  help, and the active-bucket resolver.

The parent decision `[[2026-05-19-live-iva-compensation-wallet-adr]]` (accepted)
established AEAT wallet as the primary authority and "explicit taxpayer override
with provenance" as a first-class reconciliation input, but defined no verb to
record one. This ADR fills exactly that hole; it does not revisit the authority
hierarchy.

## Constraints

- **No live AEAT write, ever.** The verb records a LOCAL decision only and
  contacts AEAT zero times, identical to `seed`/`correct`. The override is the
  taxpayer asserting a figure they are responsible for, not the app fetching one.
- **Provenance is mandatory, not optional.** `IvaCompensationOverride` already
  makes `evidence_locator` and `reason` required and non-empty; the verb MUST
  surface both as required inputs so an override is always auditable. An override
  with no recorded basis is exactly the silent under-declaration the safety gate
  exists to prevent.
- **Explicit, default-off confirmation.** Following the blast-radius-gating and
  destructive-verb discipline, the verb refuses to write without `--confirm`, and
  the help text states that an override changes the filed figure and that filing
  accuracy depends on the value supplied.
- **Single write path.** The verb MUST persist through the same
  `IvaWalletDecisionRepository` the reconciliation already owns (no parallel
  decision store), so the calculate path reads exactly one authority record per
  period — consistent with `composition-service-no-parallel-write-path`.
- **Override is bounded to the blocked case.** An override is meaningful only when
  reconciliation would otherwise block (no live wallet, or a wallet divergence the
  operator is resolving). The verb should refuse, or clearly warn, when a live
  AEAT wallet decision already covers the period, so an override cannot silently
  overrule fresh AEAT evidence.

## Implementation

Add one verb to the `iva-wallet` CLI group:

`aeat app modelo iva-wallet override --filing-year YEAR --period P --amount X
--reason "..." --evidence-locator "..." --confirm`

It constructs an `IvaCompensationOverride(amount, reason, evidence_locator,
recorded_at)`, drives `reconcile_modelo_303_iva_compensation` with that override
for the target `(303, filing_year, period)`, and persists the resulting
non-blocking `taxpayer_override` decision through the decision repository. A
subsequent `work calculate` then reads the persisted decision and applies the
amount to casilla 110, completing the carry into the dependent period.

Because the override writes a fresh decision for the period, it naturally
supersedes a stale `first_period_zero` decision recorded by an earlier calculate —
which also remedies the sticky-decision defect for the override case. The general
sticky-decision refresh (re-reconcile when the underlying seed/history changed) is
a related follow-up and should be tracked as its own plan step, not silently
folded in here.

The verb emits the standard CLI envelope with the recorded override (amount,
reason, evidence locator, decided authority, divergence) so the operator sees what
was written and which authority the next calculation will use. It never blocks on
the dependent period's verify gate, which independently still requires official
external evidence before a dependent period can be *filed* (the local override
unblocks the *calculation/carry*, not the safety gate on official filing).

The honest-pass note: this verb makes the local carry *reachable*; it does not
make a locally-overridden compensación an officially-evidenced one. A dependent
period still cannot be verified-complete on local override alone, per the
non-official-evidence discipline.

## Rationale

The carry is already correct, wired, and safety-gated — the only thing missing is
the door the gate itself points at. Adding the recording verb turns a dead-end
refusal ("requires explicit taxpayer override") into an actionable, audited
operator step, while preserving every safety property: no AEAT write, mandatory
provenance, explicit confirmation, single write path, and no override of fresh
AEAT wallet evidence. Reusing `IvaCompensationOverride`, the reconciliation's
existing override branch, and the decision repository means the verb is a thin,
low-risk recording surface over machinery the parent ADR already accepted, not new
calculation logic. The persona audit's 420→casilla-110 reconciliation is the
concrete acceptance check: with the override recorded, 2T resolves to 525.

## Consequences

- **Gain:** the two-quarter (and longer) local compensación chain becomes
  completable; the operator has a documented path out of the blocked calculation,
  and every applied carry carries an auditable reason + evidence locator.
- **Gain:** the override decision supersedes a stale per-period decision, closing
  the sticky-decision trap for the override case.
- **Difficulty / pitfall:** an override is operator-asserted, lower-confidence
  evidence; the verb must not let it masquerade as official filing evidence, and
  the dependent-period verify gate must remain unmoved. Documentation and the
  envelope wording must make the "carry unblocked, not officially evidenced"
  distinction explicit, or operators may over-trust it.
- **Pitfall:** scope creep into a live-wallet-fetch path. This ADR is local-only;
  any future live AEAT wallet read is governed by the parent ADR, not this one.
- **Opens:** a clean follow-up for the general sticky-decision refresh and for
  documenting the seed → override → calculate flow in the how-to surface.

## Codification candidates

- **Rule slug:** `iva-compensation-override-records-provenance`.
  **Rule:** Any operator-recorded IVA compensación override MUST persist a
  non-empty reason and evidence locator through the single
  `IvaWalletDecisionRepository`, default-off behind explicit confirmation, and
  MUST NOT substitute for the official external filing evidence a dependent
  period's verify gate requires.
