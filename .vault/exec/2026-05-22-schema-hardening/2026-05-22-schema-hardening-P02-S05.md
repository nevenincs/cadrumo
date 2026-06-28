---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S05'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---



# `schema-hardening` `P02.S05`

Looked up the Modelo 100 quoted-fund `coti` family and recorded that it is not
approved for generic normalization.

- Modified: `.vault/audit/2026-05-22-schema-hardening-audit.md`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P02-S05.md`

## Description

The local BOE order corpus describes a new specific Modelo 100 section for
operations involving quoted funds and quoted index SICAVs. The LIRPF corpus also
distinguishes quoted fund and quoted index SICAV treatment. The committed
registry places the exposed rows in `gp_fondos_coti`, separate from `gp_fondos`.

## Tests

Validation was manual source lookup against local BOE corpus, committed registry
labels, and prior audit records. No production code was changed in this step.
