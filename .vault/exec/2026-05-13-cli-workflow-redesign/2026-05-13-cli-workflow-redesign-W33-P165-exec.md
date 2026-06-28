---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W33.P165'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W33.P165`

Thin-CLI-exposure phase for OSS / IOSS. The wrapper has no direct
operator-facing CLI verb; the accepted consumption path is via
`aeat app modelo calculate --modelo 369`.

## Description

Per the OSS / IOSS ADR, the root contract permits only
`aeat config` and `aeat app`, and OSS / IOSS is a Modelo 369
calculation requirement rather than a standalone operator domain.
The application wrapper exposes no flags of its own; it is invoked by
the Modelo 369 calculation orchestrator the
`app modelo calculate --modelo 369 --year YYYY --period MM` path
will own (W39 modelo-calculate-revisions territory).

The boundary tests in P162 / P163 are the enforced CLI-tree
contracts:

- No parallel aggregator may sit inside the source tree.
- No `oss` / `ioss` verb may be registered under `aeat config` or
  `aeat app`, and no `app vat oss` carve-out is allowed.

Argument parsing, backend delegation, `_emit` rendering, and the
central command-error-boundary contracts are satisfied transitively
when the W39 `app modelo calculate` handler consumes the substrate.

Help-text correctness is enforced at the W39 / W47 level by the
app-modelo-shape ADR and the app-modelo-bindings-shape ADR; W33
contributes no help text of its own.

`OssIossLedgerCandidate`, `aggregate_oss_ioss_bindings`,
`validate_oss_ioss_observation`, and
`validate_oss_ioss_observations` are exported from
`aeat.application.aggregation` so the W39 calculation orchestrator
can consume them without reaching into private modules.

Closed plan rows: `W33.P165.S0985`, `W33.P165.S0986`,
`W33.P165.S0987`, `W33.P165.S0988`, `W33.P165.S0989`,
`W33.P165.S0990`.

## Tests

No new CLI tests are landed in this phase because no new CLI verb is
exposed. The two boundary regression guards covered in P162 / P163
remain the enforced contracts for the CLI tree.
