---
tags:
  - '#plan'
  - '#no-synthetic-sede-live-surfaces'
date: '2026-05-26'
modified: '2026-05-26'
tier: L2
related:
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-research]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-adr]]'
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---


# `no-synthetic-sede-live-surfaces` implementation plan

### Phase `P01` - policy invariant

Define the registry and guard invariant that AEAT-hosted live surfaces must not allow synthetic input.

- [x] `P01.S01` - Add schema validation rejecting AEAT-hosted live cross-references that allow synthetic data; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P01.S02` - Add remote-state guard validation rejecting AEAT-hosted policies that allow synthetic data; `src/aeat/domain/calculations/registry/_remote_state_guard.py`.
- [x] `P01.S03` - Update registry policy tests for the no-synthetic AEAT-host invariant; `src/aeat/domain/calculations/registry/test_remote_state_guard.py`.

### Phase `P02` - surface rewrites

Rewrite the committed Modelo 100 and Modelo 349 live-surface declarations and tests to conform to the no-synthetic-Sede rule.

- [x] `P02.S04` - Rewrite Modelo 100 Renta WEB Open registry and tests to disallow synthetic live input (7dfcaac94) - flipped `synthetic_data_allowed` to `false` with provenance comment citing the ADR; `surface remains `open_simulator`; `src/aeat/_data/registry/aeat/modelos/100/`.
- [x] `P02.S05` - Rewrite Modelo 349 GROI and IXVI registry and tests to disallow synthetic live input (7dfcaac94) - flipped both `modelo-349-groi-spanish-counterparty-check` and `modelo-349-ixvi-foreign-counterparty-check` to `synthetic_data_allowed = false`; `both retain `authenticated_simulator` classification; `src/aeat/_data/registry/aeat/modelos/349/`.
- [x] `P02.S06` - Rewrite outbound Sede live-surface tests and drivers to avoid live synthetic input; `src/aeat/adapters/outbound/aeat/sede/`.

### Phase `P03` - validation and handoff

Run the focused validation gates, record execution evidence, and close the declaration-extraction S124 handoff only after implementation is verified.

- [x] `P03.S07` - Run focused registry and Sede test gates for the no-synthetic policy: registry invariant, Modelo 100/349, registry oracle/applicability/parity, committed registry, GROI, NIF-IVA, and Renta WEB Open offline Sede gates passed; `broader Sede declarations batch still has three unrelated Modelo 303 export-layout failures on `modelo-303-envelope-marker`; `validation residual tracked out of scope`.
- [x] `P03.S08` - Record execution evidence and close the declaration-extraction S124 handoff; `.vault/exec/`.

### Phase `P04` - live IVA read-only follow-through

Bind the no-synthetic policy to the live IVA work so the wallet/filed-history
driver cannot regress into AEAT-hosted synthetic preview, filing, payment, or
representation submissions while hardening the read-only acquisition backend.

- [x] `P04.S09` - Verify live IVA wallet and filed-history drivers use only configured read-only/authentication action classes and no synthetic AEAT-hosted inputs; `src/aeat/adapters/outbound/aeat/sede src/aeat/domain/calculations/registry/_remote_state_guard.py`.
- [x] `P04.S10` - Add a constants-centralization guard for AEAT-hosted live-surface hosts, routes, and read-action markers discovered during the live IVA work. Partial 2026-05-26: live Sede executable-literal guard covers core settings, Cl@ve, declarations, wallet, parser, and verify paths; `GROI and filed-history test constants were moved to registry-derived values; broader test fixture inventory remains open; `src/aeat/core/external_constants.toml src/aeat/tests`.
- [x] `P04.S11` - Re-run no-synthetic live-surface gates after live IVA auth/acquisition changes; `src/aeat/domain/calculations/registry src/aeat/adapters/outbound/aeat/sede`.
