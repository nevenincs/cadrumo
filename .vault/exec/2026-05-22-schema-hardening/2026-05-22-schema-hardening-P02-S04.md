---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S04'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---



# `schema-hardening` `P02.S04`

Looked up the official Modelo 200 maintenance-employment source context and
recorded the policy decision for the `con`/`sin` maintenance-employment rows.

- Modified: `.vault/audit/2026-05-22-schema-hardening-audit.md`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P02-S04.md`

## Description

The official Sociedades 2024 manual distinguishes the `RDL 6/2010` regime with
employment maintenance from the `RDL 13/2010` regime without that requirement.
The committed registry mirrors the distinction across casillas `02631` through
`02650`. The step approves removing global `sin` optional stripping and marking
the 12 exposed correction rows as explicit intentional singletons.

## Tests

Validation was manual source lookup against the official local manual extract
and committed registry labels. No production code was changed in this step.
