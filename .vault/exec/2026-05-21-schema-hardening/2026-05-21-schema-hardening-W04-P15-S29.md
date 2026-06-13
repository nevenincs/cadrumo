---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S29'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W04.P15.S29`

Recorded the Renta 2025 manual source text and registry context for the
Catalunya generated/pending pair.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W04-P15-S29.md`

## Description

The lookup tied IDs `2004` and `2005` to the Catalunya deduction for investment
in agricultural and housing cooperative societies. The audit records the
manual title, normative basis, carryforward text, Anexo B.14 transfer context,
and registry adjacency to ID `2003`.

## Tests

Validated the source rows by reading the registry TOML entries and extracting
the relevant Renta 2025 manual text with `pdftotext`. Plan and frontmatter
checks are run at the end of the phase.
