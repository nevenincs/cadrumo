---
generated: true
tags:
  - '#index'
  - '#iva-compensation-override-cli'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:7afc8f5aabf900b5f1c1e4ff3fc101a712024da746829026a0de443f27c68438'
related:
  - '[[2026-06-19-iva-compensation-override-cli-adr]]'
  - '[[2026-06-19-iva-compensation-override-cli-audit]]'
  - '[[2026-06-19-iva-compensation-override-cli-plan]]'
  - '[[2026-07-10-iva-compensation-override-cli-research]]'
---

# `iva-compensation-override-cli` feature index

Auto-generated index of all documents tagged with `#iva-compensation-override-cli`.

## Documents

### adr

- `2026-06-19-iva-compensation-override-cli-adr` - `iva-compensation-override-cli` adr: `Operator-facing IVA-wallet override verb for cross-period compensación carry` | (**status:** `accepted`)

### audit

- `2026-06-19-iva-compensation-override-cli-audit` - `iva-compensation-override-cli` audit: `Adversarial review: P01 override recorder reverted (missing guard, sticky-shadow, redundant)`

### exec

- `2026-06-19-iva-compensation-override-cli-P01-S01` - Add record_iva_compensation_override_for_bucket: resolve NIF, build IvaCompensationOverride(amount, reason, evidence_locator, recorded_at), drive reconcile_modelo_303_iva_compensation with override and persist the taxpayer_override decision
- `2026-06-19-iva-compensation-override-cli-P01-S02` - Emit a MODELO_IVA_WALLET override audit event carrying reason and evidence_locator provenance through the single BucketEventHistoryRepository
- `2026-06-19-iva-compensation-override-cli-P01-S03` - Add a behaviour test: record override then assert the persisted taxpayer_override decision unblocks calculate and applies the amount to casilla 110 (persona 2T resolves to 525)
- `2026-06-19-iva-compensation-override-cli-P01-S08` - Precondition: promote IvaCompensationOverride to the domain.iva_compensation package __all__ re-export so the application recorder consumes it via the top-level facade, not the private submodule
- `2026-06-19-iva-compensation-override-cli-P02-S04` - Register the iva-wallet override Typer verb with --filing-year --period --amount --reason --evidence-locator and mandatory default-off --confirm, refusing to overrule a fresh AEAT wallet decision
- `2026-06-19-iva-compensation-override-cli-P02-S05` - Add the IvaWalletOverrideResult output schema and register it for JSON-schema conformance
- `2026-06-19-iva-compensation-override-cli-P02-S06` - Author override help/confirm/error locale leaves for en es ca hu via python -m aeat.locales set, then scaffold --check clean
- `2026-06-19-iva-compensation-override-cli-P02-S07` - Add a CLI conformance test exercising the override verb end to end and run the documented-command conformance gate

### plan

- `2026-06-19-iva-compensation-override-cli-plan` - `iva-compensation-override-cli` plan

### research

- `2026-07-10-iva-compensation-override-cli-research` - iva-compensation-override-cli research: warning closeout research grounding
