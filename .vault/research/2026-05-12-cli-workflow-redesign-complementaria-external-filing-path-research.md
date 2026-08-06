---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-07-17'
body_hash: 'sha256:4af115295596f05294b9637d72179b5e8532b49041c46b449cd00fcd8f8aadeb'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `complementaria-external-filing-path`

## Findings

The complementaria builder requires a locally persisted original draft and
matching schema snapshot. That blocks amendments for returns originally filed
outside the tool, even though justificante import and filing records can provide
official evidence.

Target command is already the canonical app-modelo shape:
`app modelo amend --kind complementaria --from-filing-record ID`. The command
must consume imported filing records, official justificante/CSV minimum fields,
bucket events, and schema compatibility checks.

Reject live submit, legacy `aeat filing complementaria submit`, amendment
without official justificante/CSV minimum fields, or shims that fabricate a
local original draft from incomplete evidence.
