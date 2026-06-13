---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `modelo-145-foundation`

## Findings

`registry/aeat/modelos/145.toml` is absent. AEAT describes Modelo 145 as an
IRPF communication of work-income withholding data to the payer or variation of
previously communicated data. AEAT also states it does not require presentation
to the tax administration and that the payer keeps a copy. Source:
`https://sede.agenciatributaria.gob.es/Sede/procedimientos/G603.shtml`.

Target implementation is a Modelo 145 registry file, form schema, and
profile/binding contract for employee withholding communication. It is a
non-filing communication workflow, not a live AEAT submission.

Reject folding Modelo 145 into Modelos 111/190, using profile-only fields
without a registry/modelo foundation, or adding filing-submission shims.
