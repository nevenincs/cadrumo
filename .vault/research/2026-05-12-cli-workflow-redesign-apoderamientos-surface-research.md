---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `apoderamientos-surface`

## Findings

The config-auth ADR reserves apoderamientos. Current Cl@ve code supports
own-name representation and refuses representative selection.

AEAT exposes a Registro de apoderamientos with registration, consultation,
extension, revocation, confirmation, and renunciation workflows. Source:
`https://sede.agenciatributaria.gob.es/Sede/colaborar-agencia-tributaria/registro-apoderamientos.html`.

Target placement is `aeat config auth apoderado ...` for local
identity/representation configuration plus read-only live checks. The CLI may
store which represented identity the bucket intends to operate for and may
check representation status, but it must not submit registration, extension,
revocation, confirmation, or renunciation operations.

Reject automatic representation form submission, `app live apoderamientos`
mutation, filing-as-representative shortcuts, and shims that bypass explicit
representation configuration.
