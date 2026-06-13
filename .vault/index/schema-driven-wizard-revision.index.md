---
generated: true
tags:
  - '#index'
  - '#schema-driven-wizard-revision'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - '[[2026-05-12-schema-driven-wizard-revision-adr]]'
  - '[[2026-05-12-schema-driven-wizard-revision-phase1-step1-exec]]'
  - '[[2026-05-12-schema-driven-wizard-revision-phase1-step10-exec]]'
  - '[[2026-05-12-schema-driven-wizard-revision-phase1-step11-exec]]'
  - '[[2026-05-12-schema-driven-wizard-revision-phase1-step12-exec]]'
  - '[[2026-05-12-schema-driven-wizard-revision-phase1-step13-exec]]'
  - '[[2026-05-12-schema-driven-wizard-revision-phase1-step14-exec]]'
  - '[[2026-05-12-schema-driven-wizard-revision-phase1-step15-exec]]'
  - '[[2026-05-12-schema-driven-wizard-revision-phase1-step2-exec]]'
  - '[[2026-05-12-schema-driven-wizard-revision-phase1-step3-exec]]'
  - '[[2026-05-12-schema-driven-wizard-revision-phase1-step4-exec]]'
  - '[[2026-05-12-schema-driven-wizard-revision-phase1-step5-exec]]'
  - '[[2026-05-12-schema-driven-wizard-revision-phase1-step6-exec]]'
  - '[[2026-05-12-schema-driven-wizard-revision-phase1-step7-exec]]'
  - '[[2026-05-12-schema-driven-wizard-revision-phase1-step8-exec]]'
  - '[[2026-05-12-schema-driven-wizard-revision-phase1-step9-exec]]'
  - '[[2026-05-12-schema-driven-wizard-revision-plan]]'
  - '[[2026-06-04-schema-driven-wizard-revision-research]]'
---

# `schema-driven-wizard-revision` feature index

Auto-generated index of all documents tagged with `#schema-driven-wizard-revision`.

## Documents

### adr

- `2026-05-12-schema-driven-wizard-revision-adr` - `schema-driven-wizard-revision` adr

### exec

- `2026-05-12-schema-driven-wizard-revision-phase1-step1-exec` - r1 strip transient-process-state markers from test_config_setter
- `2026-05-12-schema-driven-wizard-revision-phase1-step10-exec` - r10 sweep dead next-action guidance
- `2026-05-12-schema-driven-wizard-revision-phase1-step11-exec` - r11 relocate setup-status surface into wizard module
- `2026-05-12-schema-driven-wizard-revision-phase1-step12-exec` - r12 excise legacy autonomo helpers; fix wizard-introduced regressions
- `2026-05-12-schema-driven-wizard-revision-phase1-step13-exec` - r13 relocate namespace constants and delete application/setup/
- `2026-05-12-schema-driven-wizard-revision-phase1-step14-exec` - r14 fold cli root surfaces to config + app only
- `2026-05-12-schema-driven-wizard-revision-phase1-step15-exec` - r15 final verification sweep
- `2026-05-12-schema-driven-wizard-revision-phase1-step2-exec` - r2 excise historical phrasing from production source
- `2026-05-12-schema-driven-wizard-revision-phase1-step3-exec` - r3 convert raw assert to typed guard in compiler
- `2026-05-12-schema-driven-wizard-revision-phase1-step4-exec` - r4 replace monkeypatch.setattr purity test with structural assertion
- `2026-05-12-schema-driven-wizard-revision-phase1-step5-exec` - r5 delete trivially-ok verifier checks
- `2026-05-12-schema-driven-wizard-revision-phase1-step6-exec` - r6 deduplicate _normalise_key
- `2026-05-12-schema-driven-wizard-revision-phase1-step7-exec` - r7 excise the ignored-path-arg shims
- `2026-05-12-schema-driven-wizard-revision-phase1-step8-exec` - r8 descriptor-driven typer flag derivation
- `2026-05-12-schema-driven-wizard-revision-phase1-step9-exec` - r9 land cli.config locale catalogue and broaden parity audit

### plan

- `2026-05-12-schema-driven-wizard-revision-plan` - schema-driven wizard revision plan

### research

- `2026-06-04-schema-driven-wizard-revision-research` - `schema-driven-wizard-revision` research: `phase two research grounding`  ## Question  Which ADR-only feature finding needs an explicit live research record so VaultSpec semantic search can brief future work from an evidence node instead of an orphaned decision?  ## Findings  This note is a Phase Two vault-curation grounding record. It does not introduce new runtime behavior, change accepted architecture, or supersede a deeper feature-specific research note.  The feature health check reported an ADR without a same-feature research document. Live ADR records linked in frontmatter remain the decision sources; this research record makes the evidence path explicit and searchable.  If archived records exist for this feature, they remain historical/reference evidence only. They are not treated as current authority unless a live ADR explicitly re-enrols them.  Body wiki-links are intentionally avoided. The authoritative navigation edge is carried by frontmatter so body-link hygiene remains clean.  ## Recommendation  Keep this record as the active research bridge until a deeper feature-specific research document supersedes it and updates the related frontmatter on the ADR and index records.
