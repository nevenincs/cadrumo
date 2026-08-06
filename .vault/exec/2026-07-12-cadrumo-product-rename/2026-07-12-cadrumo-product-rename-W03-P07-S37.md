---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-13'
body_hash: 'sha256:b15033d41df4bb14939b69626ba0ec793ffa39dd4851e94fed9347a378d6a034'
step_id: 'S37'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update the slim-wheel clean-install probe to Cadrumo names

## Scope

- `dev/packaging/smoke_core.py`

## Description

- Read the binding naming ADR and confirm that `aeat` is the sole human
  executable while `CADRUMO` is the version identity.
- Correct the slim-wheel installed CLI assertion to require `CADRUMO` from
  `aeat --version`.
- Run focused packaging tests, lint, formatting, and the real wheel build and
  fresh virtual-environment installation probe.

## Outcome

The slim-wheel probe now verifies the installed `aeat` executable and rejects
version output that does not carry the `CADRUMO` identity. The focused packaging
suite passed three tests, Ruff and formatting passed, and the real packaging
smoke built `cadrumo-0.2.0-py3-none-any.whl`, installed it into a fresh virtual
environment, exercised the installed CLI, and wrote its smoke manifest.

## Notes

The real smoke completed in 312 seconds. Existing authority-owned `AEAT` and
`registry/aeat` names were not changed. Sentence prose casing was outside this
Step; the uppercase assertion is intentional because version output is an
identity context under the binding ADR.

## Plan chronology correction from S94

The S37 checkbox was first cross-carried as closed by parent S87 commit
`03cd792be3`, before this Step's owning implementation commit `a4e56dcf83`.
That early plan hunk was not implementation evidence. Commit `a4e56dcf83`
delivered the probe and this refreshed record, and independent audit
`46363217dd` passed the installed-wheel contract. The current checked state is
supported by those later S37-owned artifacts even though the earlier checkbox
attribution was defective.
