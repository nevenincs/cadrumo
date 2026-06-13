---
tags:
  - '#research'
  - '#no-synthetic-sede-live-surfaces'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-auth-gated-acquisition-status-audit]]'
  - '[[2026-05-07-live-parity-oracle-adr]]'
---

# `no-synthetic-sede-live-surfaces` research: `prohibit synthetic data on AEAT-hosted live surfaces`

Researched the impact of the hard operator constraint that synthetic data must
not be sent to Sede or AEAT-hosted form surfaces. The immediate declaration
fixture acquisition rows are already blocked without synthetic preview/PDF
generation. This research covers the broader live-parity surfaces surfaced by
that constraint.

## Findings

### Current Conflict

Three committed registry cross-references currently declare
`synthetic_data_allowed = true` on AEAT-hosted live surfaces:

| Surface | Registry entry | Classification | Hosts | Current posture |
| --- | --- | --- | --- | --- |
| Modelo 100 Renta WEB Open | `modelo-100-renta-web-open` | `open_simulator` | `sede.agenciatributaria.gob.es`, `www2.agenciatributaria.gob.es` | Synthetic profile payloads are accepted for live parity. |
| Modelo 349 GROI Spanish-counterparty check | `modelo-349-groi-spanish-counterparty-check` | `authenticated_simulator` | `www2.agenciatributaria.gob.es` | Arbitrary Spanish NIF input is treated as acceptable live query data. |
| Modelo 349 IXVI foreign-EU VAT-ID check | `modelo-349-ixvi-foreign-counterparty-check` | `authenticated_simulator` | `sede.agenciatributaria.gob.es`, `www1.agenciatributaria.gob.es` | Arbitrary EU VAT-ID input is treated as acceptable live query data. |

These entries are not incidental. They follow the accepted live-parity oracle
architecture and the 2026-05-07 authenticated-synthetic-surface taxonomy.
Changing them requires ADR supersession or amendment, not only TOML edits.

### Declaration Acquisition Impact

For modelos 180, 036, 369, 720, and 840, the no-synthetic-Sede rule removes
the former live preview/download acquisition path. Remaining legal acquisition
paths are:

- operator-provided authorised fixtures produced outside this automation
  session;
- authenticated read-only retrieval of operator-owned filed declarations;
- static official PDFs, record designs, BOE annexes, manuals, and procedure
  pages when those artifacts directly match the parser surface being claimed.

### Live Parity Impact

Renta WEB Open, GROI, and IXVI can no longer be used as live synthetic oracles
under the new constraint. Existing captured replay payloads may remain usable
as local fixtures if they are already in the corpus, source-tracked, and do not
require new live submission of synthetic inputs. New live captures must be
limited to non-synthetic, operator-authorised data, or skipped.

### Recommended Direction

Adopt a hard registry invariant:

- Any cross-reference whose allowed host is under `agenciatributaria.gob.es` or
  `aeat.es` must declare `synthetic_data_allowed = false`.
- `open_simulator` and `authenticated_simulator` remain possible surface
  classifications, but only for non-synthetic operator-authorised input or
  local replay of previously acquired evidence.
- Remote-state guards should reject live operations when the policy advertises
  synthetic input, rather than relying on call-site discipline.
- Tests that currently construct `RemoteStateGuardPolicy` with
  `synthetic_data_allowed=True` for AEAT-hosted hosts should be changed to
  local replay, static-source, or non-AEAT-host examples.

### Work Required After ADR Approval

- Supersede or amend the 2026-05-07 authenticated-synthetic-surface taxonomy
  ADR.
- Update Modelo 100 and Modelo 349 registry live cross-references to
  `synthetic_data_allowed = false`.
- Update `RemoteStateGuardPolicy` validation so AEAT-hosted policies cannot
  permit synthetic data.
- Update Renta WEB Open, GROI, and IXVI live tests and drivers to avoid live
  synthetic input.
- Preserve local replay parity where captured evidence is already available
  and legally retained.
