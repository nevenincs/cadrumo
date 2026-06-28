---
tags:
  - '#research'
  - '#live-parity-oracle'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-06-live-parity-oracle-backend-adr]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-adr]]'
  - '[[2026-05-04-live-filing-data-capture-adr]]'
---



# `live-parity-oracle` research: `read-only AEAT verification backend`

## Scope

This research backfills the design basis for the accepted live-parity oracle
ADR. The implementation surface is the modelo-agnostic backend that lets
calculation-registry tests compare registry-rendered payloads against
AEAT-published read-only surfaces without creating any submit, mutate, or
session-write capability.

## Findings

The calculation truth registry already requires every modelo to identify the
authority tier behind its fields and formulas. Static evidence is sufficient
for registry structure, legal references, and deterministic workbook parity.
Some model behaviour still needs a live read oracle because AEAT can expose
server-side validation or calculation behaviour that is not fully captured by
published workbook files.

The project already has a remote-state guard that denies write-like HTTP
methods, forbidden action tokens, and non-AEAT hosts. That guard is necessary
but not sufficient as an application contract. A live parity backend also needs
typed inputs, typed verdicts, source provenance, deterministic replay metadata,
and a single adapter boundary so individual modelos cannot grow bespoke
network code paths.

The backend must therefore remain read-only, modelo-agnostic, and evidence
oriented. It should return parity observations that can be consumed by tests
and vault audits without coupling calculation logic to browser automation or
remote transport details.

## Implications

The ADR should require one shared oracle contract, one verdict shape, and
explicit remote-state guard enforcement at every live read boundary. It should
also keep local export and live submission separate: live parity verifies
calculation conformance, while user-directed export remains the only output
artifact workflow.
