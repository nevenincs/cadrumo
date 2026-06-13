---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-live-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `Borrador 100 snapshot binding integration into app modelo calculate` | (**status:** `accepted`)

## Problem Statement

`aeat app live borrador 100 fetch` captures an AEAT datos-fiscales /
borrador-100 snapshot into the active bucket and returns a SNAPSHOT_ID.
`aeat app modelo calculate --modelo 100 --year YYYY --period annual`
runs the modelo 100 calculation. The apex does not specify how a
captured borrador snapshot becomes a binding input that `calculate`
consumes. Operators filing IRPF anual cannot pre-fill the calculation
from AEAT's own data without this integration.

## Considerations

- The borrador snapshot contains AEAT-supplied datos-fiscales values
  (rentas del trabajo, retenciones, datos personales) that duplicate
  ledger-derived inputs but carry AEAT authority.
- Modelo 100 has bindings whose canonical source is "previous AEAT
  filing" or "AEAT pre-fill". For those bindings the borrador snapshot
  is the authoritative source; ledger-derived values must defer.
- Other bindings (e.g. self-employed income from `_renta_ledger`) are
  ledger-authoritative; the borrador must not override them.
- The integration must preserve source provenance: the calculation
  revision's source trace must record which casillas came from
  borrador vs. ledger vs. profile vs. operator override.

## Constraints

- The integration is exclusive to modelo 100. Other modelos do not
  consume borrador snapshots through this path.
- The borrador snapshot is consumed only when the operator names it
  via `--borrador SNAPSHOT_ID` on `aeat app modelo calculate`. Implicit
  auto-consumption is rejected.
- Binding precedence inside a single calculate invocation:
  `--binding KEY=VALUE` (operator override) > borrador snapshot >
  ledger aggregation > profile facts > registry defaults.
- The registry-declared binding source kind determines borrador
  eligibility. Bindings tagged `aeat_prefilled = true` accept borrador
  values; all other bindings reject them.
- The borrador snapshot must be in the active bucket and must not be
  superseded by a later capture for the same modelo/year/period; the
  command rejects superseded snapshot ids with a fix pointer to
  `aeat app live borrador 100 list`.
- The calculation revision records the `borrador_snapshot_id` in its
  source trace, alongside each casilla value sourced from the
  snapshot.
- Live AEAT submission remains permanently forbidden.

## Implementation

Command shape extension on `aeat app modelo calculate`:

```text
aeat app modelo calculate --modelo 100 --year YYYY --period annual
                          [--borrador SNAPSHOT_ID]
                          [--binding KEY=VALUE ...]
                          [--format json|text]
```

Pipeline within `application/filing/_calculate.py`:

- Resolve the borrador snapshot through the borrador application
  repository.
- For each registry binding with `aeat_prefilled = true`, attempt
  borrador resolution: if the snapshot carries the canonical key,
  populate the binding and record `borrador_snapshot_id` plus the
  source path in the revision's source trace.
- Apply ledger / profile / override precedence per the rules above
  for remaining bindings.
- Emit a `modelo.calculation.created` bucket event with the
  calculation revision id, a flag indicating borrador participation,
  and the snapshot id.

JSON output extensions:

- The calculate response envelope includes `borrador_snapshot_id` and
  `bindings_sourced_from_borrador: [...]` naming the bindings the
  snapshot resolved.

`aeat app modelo bindings list --modelo 100 --year YYYY --period
annual` extension:

- Each binding row tagged `aeat_prefilled = true` includes a column
  `borrador_capable: true`.
- The readiness category `live observation` for those bindings carries
  a fix pointer chain: `aeat app live borrador 100 fetch` → `aeat app
  modelo calculate --borrador SNAPSHOT_ID`.

## Rationale

Modelo 100 is the highest-value annual filing for an autónomo. AEAT
publishes datos-fiscales as a borrador every year; reproducing those
values manually from ledger inputs is error-prone and ignores the
authoritative source. Wiring the snapshot as an explicit calculate
input preserves operator control (no implicit consumption), keeps
source provenance auditable in the revision trace, and closes the
most-cited operational gap in the IRPF annual path. Narrow scope
(modelo 100 only, explicit opt-in flag, registry-driven binding
eligibility) prevents borrador values from leaking into modelos where
they are not authoritative.

## Consequences

- The borrador application repository and snapshot persistence gain a
  consumer in the calculate path; bucket migration is unaffected.
- The modelo 100 registry must annotate `aeat_prefilled = true` on the
  appropriate bindings.
- Operator help on `aeat app modelo calculate --modelo 100` includes a
  "First time? Fetch the borrador with `aeat app live borrador 100
  fetch` and pass `--borrador SNAPSHOT_ID`." hint.
- Tests must cover: explicit borrador consumption populates eligible
  bindings; ineligible bindings reject borrador values; override
  precedence holds; superseded snapshots are rejected; source trace
  records the snapshot id for every borrador-sourced casilla; bucket
  event carries the snapshot reference.
