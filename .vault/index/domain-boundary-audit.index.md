---
generated: true
tags:
  - '#index'
  - '#domain-boundary-audit'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:b91472c85bd0bcfed97d08e56cd5b1a31f57acc3b5baba07e978003af7a60ccc'
related:
  - '[[2026-06-01-domain-boundary-audit-W10-P33-S109]]'
  - '[[2026-06-01-domain-boundary-audit-W11-P37-S108]]'
  - '[[2026-06-01-domain-boundary-audit-adr]]'
  - '[[2026-06-01-domain-boundary-audit-audit]]'
  - '[[2026-06-01-domain-boundary-audit-plan]]'
  - '[[2026-06-04-domain-boundary-audit-research]]'
---

# `domain-boundary-audit` feature index

Auto-generated index of all documents tagged with `#domain-boundary-audit`.

## Documents

### adr

- `2026-06-01-domain-boundary-audit-adr` - `domain-boundary-audit` adr: `AEAT hexagonal ownership and layering contract` | (**status:** `accepted`)

### audit

- `2026-06-01-domain-boundary-audit-audit` - `domain-boundary-audit` audit: `Domain ownership and cross-boundary outlier audit`

### exec

- `2026-06-01-domain-boundary-audit-W10-P33-S109` - Investigate the 13 pre-existing test_cli_surface ledger-lifecycle 'No active bucket session is open' failures (test_app_ledger_lifecycle_reset_*, test_app_ledger_import_reimport_*). Proven unrelated to W10 (fail identically on the old import) but only 1 of 13 individually confirmed
- `2026-06-01-domain-boundary-audit-W11-P37-S108` - Prune/update the stale .importlinter ignore entries that W11's repoint left unmatched: the domain repo edges now target the top-level package, so entries naming aeat.adapters.persistence.storage.envelope / .sql / .envelope._envelope for filing/justificante/submission/buckets/transactions/invoices _repository are unmatched (the 15->22 unmatched-ignore warning bump). Update each to the current '-> aeat.adapters.persistence.storage' edge (or delete if the new edge is deferred/unflagged)

### plan

- `2026-06-01-domain-boundary-audit-plan` - `domain-boundary-audit` `Domain boundary remediation` plan

### research

- `2026-06-04-domain-boundary-audit-research` - `domain-boundary-audit` research: `phase two research grounding`  ## Question  Which ADR-only feature finding needs an explicit research record so VaultSpec semantic search can brief future work from an evidence node instead of an orphaned decision?  ## Findings  This note is a Phase Two vault-curation grounding record. It does not introduce new runtime behavior, change accepted architecture, or supersede a deeper feature-specific research note.  The feature health check reported an ADR without a same-feature research document. The linked ADR records in frontmatter remain the decision sources; this research record makes the evidence path explicit and searchable.  Body wiki-links are intentionally avoided. The authoritative navigation edge is carried by frontmatter so body-link hygiene remains clean.  ## Recommendation  Keep this record as the active research bridge until a deeper feature-specific research document supersedes it and updates the related frontmatter on the ADR and index records.
