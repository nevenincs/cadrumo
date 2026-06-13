---
tags:
  - '#exec'
  - '#core-authority'
step_id: S09
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W02.P03.S09 — ResourceNotFoundError -> CoreNotFoundError

## Change

`ResourceNotFoundError(ResourceLoadError)` → `(ResourceLoadError, CoreNotFoundError)`.

MRO: ResourceNotFoundError -> ResourceLoadError -> CoreNotFoundError
     -> CoreError -> AeatError -> KeyError -> LookupError -> Exception.

One existing catch site at application/overview/_explain.py:163 verified — no
regression since catch is on the specific type.

## Deviation from plan

Plan said "first domain NotFoundError subclass". ResourceNotFoundError is in
core/resources/, not domain/. Executed against the ER-03 semantic pair.

## Verification gate

resources + overview tests: exit code 0 (background task b2shwe8rr).

## Commit

`46ecf5d39` — feat(errors): W02.P03.S09 ResourceNotFoundError -> CoreNotFoundError
