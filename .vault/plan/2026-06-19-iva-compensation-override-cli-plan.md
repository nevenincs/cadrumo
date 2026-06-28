---
tags:
  - '#plan'
  - '#iva-compensation-override-cli'
date: '2026-06-19'
modified: '2026-06-19'
tier: L2
related:
  - '[[2026-06-19-iva-compensation-override-cli-adr]]'
---








# `iva-compensation-override-cli` plan

### Phase `P01` - Application recorder + persistence

Record an explicit taxpayer override as a persisted taxpayer_override IVA-wallet decision so the calculate path applies the cross-period carry, with mandatory provenance and an audit event.



- [ ] `P01.S01` - Add record_iva_compensation_override_for_bucket: resolve NIF, build IvaCompensationOverride(amount, reason, evidence_locator, recorded_at), drive reconcile_modelo_303_iva_compensation with override and persist the taxpayer_override decision; `src/aeat/application/modelo/_iva_wallet_seed.py`.
- [ ] `P01.S02` - Emit a MODELO_IVA_WALLET override audit event carrying reason and evidence_locator provenance through the single BucketEventHistoryRepository; `src/aeat/application/modelo/_iva_wallet_seed.py`.
- [ ] `P01.S03` - Add a behaviour test: record override then assert the persisted taxpayer_override decision unblocks calculate and applies the amount to casilla 110 (persona 2T resolves to 525); `src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py`.
- [ ] `P01.S08` - Precondition: promote IvaCompensationOverride to the domain.iva_compensation package __all__ re-export so the application recorder consumes it via the top-level facade, not the private submodule; `src/aeat/domain/iva_compensation/__init__.py`.

### Phase `P02` - Operator CLI surface + locales + conformance

Expose the recorder as the iva-wallet override verb with localized help/errors and conformance coverage, mirroring the seed/correct verbs.

- [ ] `P02.S04` - Register the iva-wallet override Typer verb with --filing-year --period --amount --reason --evidence-locator and mandatory default-off --confirm, refusing to overrule a fresh AEAT wallet decision; `src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py`.
- [ ] `P02.S05` - Add the IvaWalletOverrideResult output schema and register it for JSON-schema conformance; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [ ] `P02.S06` - Author override help/confirm/error locale leaves for en es ca hu via python -m aeat.locales set, then scaffold --check clean; `src/aeat/locales`.
- [ ] `P02.S07` - Add a CLI conformance test exercising the override verb end to end and run the documented-command conformance gate; `src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py`.

## Description

Implement the operator-facing IVA-wallet override verb decided in the
`iva-compensation-override-cli` ADR. The Modelo 303 cross-period compensación
carry is fully wired and safety-gated, but a local-only filer cannot complete it:
the reconciliation correctly blocks auto-applying a seeded or local prior balance
without live AEAT wallet evidence, and no CLI verb records the explicit taxpayer
override the block demands. The override machinery already exists end to end
(`IvaCompensationOverride` -> `_override_reconciliation_decision` -> persisted
`taxpayer_override` decision -> `apply_iva_compensation_decision_binding` writes
casilla 110); this plan adds the thin recording surface over it. The work mirrors
the existing `seed` and `correct` verbs (application wrapper in
`_iva_wallet_seed.py`, Typer verb in `_modelo_iva_wallet_cli.py`, locale leaves
via the `aeat.locales` CLI, conformance tests). It carries the safety invariants
from the ADR: mandatory provenance (reason + evidence locator), default-off
`--confirm`, single decision write path, no AEAT write, and no override of a
fresh AEAT wallet decision. The sticky-persisted-decision refresh and the
dependent-period verify gate (which still requires official external evidence)
are explicitly out of scope here.

## Steps







## Parallelization

Phase `P01` (the application recorder and its behaviour test) must land before
Phase `P02` (the CLI surface), because the verb wraps the recorder. Within `P01`,
the precondition `S08` (promote the override symbol to the package facade) runs
first, then `S01`, then `S02` and `S03`. Within `P02`, `S04` and `S05` may proceed
together; `S06` (locales) gates `S07` (the conformance test renders localized
help). The whole feature must not be sequenced ahead of, or merged into, the
active peer cross-period-filing-deadlock work that touches the same subsystem;
coordinate so the two land independently.

## Verification

- `P01`: a real save -> load behaviour test shows recording an override persists
  exactly one `taxpayer_override` decision for the period, and a subsequent
  `work calculate` applies the amount to casilla 110 (the persona 2T resolves to
  525, not 945). The override decision supersedes a stale `first_period_zero`
  decision for that period.
- `P01`: the override write emits one audit event carrying the reason and
  evidence locator; an override with empty reason or evidence locator is refused
  at the model boundary.
- `P02`: `python -m aeat.locales scaffold --check` and `audit` exit clean after
  the new leaves land; inter-locale and honesty parity gates stay green.
- `P02`: the documented-command conformance gate and the JSON-schema conformance
  gate pass for the new verb; the CLI conformance test drives the verb end to end
  and asserts the envelope reports the recorded override and the decided
  authority.
- The verb contacts AEAT zero times and refuses to overrule a fresh AEAT wallet
  decision; the dependent-period verify gate is unchanged (local override
  unblocks the calculation/carry, never the official-filing safety gate).
- The plan is complete when every Step is closed and a fresh-context review
  confirms the safety invariants from the ADR hold.
