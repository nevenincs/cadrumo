---
tags:
  - '#audit'
  - '#registry-edition-authoring'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:82e154ecf5526f70fb348e1bd17dc309f4d44266225d31f05d737d4b80071f47'
related: []
---

# Registry authoring governance review

## Scope

Reviewed all 20 project-owned rules under `.vaultspec/rules` and registry-specific workflow wording under `.vaultspec/skills`. Changed 12 rules and the continuity workflow. Preserved installation-owned rules, skills and templates; no registry data, compiler implementation or published authority was changed by this governance pass. Existing concurrent source and continuity-workflow edits were preserved.

The unchanged rules cover orchestration, aggregation, CLI, ledger, locales, naming, centralisation and worktree ownership; their current invariants did not require registry-specific changes. No registry-specific scaffolding defect was found in the templates. This is a governance correction, not a new registry migration or a claim that runtime publication is complete.

## Findings

### authoring-bootstrap | high | Published runtime authority was conflated with editable source

Resolved in `aeat-registry-authority-flow`, `aeat-calculation-grounding` and the continuity workflow. Current source inspection uses `inspect_authoring_candidate` whether or not a published generation exists. Inspection, validated compilation, installation and publication now have distinct meanings. The inspected compiler implementation uses canonical structural compilation and registry validation without requiring a published pointer. Validation findings remain visible and cannot be promoted into runtime authority.

### storage-and-projection | high | Missing authored data and missing legal evidence were conflated

Resolved in the authority, bindings, export, no-silent-under-declaration and no-legacy rules. The wording distinguishes payload inheritance from legal continuity, temporal gaps from explicit deletions, historical baselines from obsolete duplicates, and projected availability from operation eligibility. The single canonical support declaration owns consumer ranges. These are authoring and acceptance requirements, not a claim that this prose edit independently proves every runtime consumer.

### acceptance-boundaries | medium | Aggregate success or failure obscured the actual deliverable

Resolved in quality, documentation and execution rules. Source equivalence is separate from independent minimality and stable-input verification. Contract-defined sequence order is not arbitrary mapping-key serialization order. Unchanged publication defects are classified separately from representation regressions; publication itself retains full validation. A wait timeout is not a failed process and a scratch artifact is not installed source.

### security-and-ownership | medium | Broad wording could misclassify public sources or overwrite concurrent edits

Resolved in the sensitive-data and no-destructive-git rules. Public AEAT/BOE evidence is distinguished from private taxpayer data, and local registry operations from real filing submission. The suggested temporary overwrite-and-restore procedure was replaced with isolated reproduction. Destructive Git prohibitions remain intact.

### workflow-commands | medium | Continuity test paths were obsolete

Resolved in the continuity skill. Commands now address `dev/registry/tests` and explicitly clear default selection options. Collection using those paths and options succeeded: 86 tests collected, exit 0. This was collection validation, not execution of the tax-data regression suite.

## Recommendations

Keep `aeat-registry-authority-flow` as the shared home for registry state and authoring boundaries; workflow prose references it rather than adding another authority model. No additional rule, compatibility layer or publication bypass is needed for these findings.

Validation completed: skill-creator quick validation passed; `git diff --check` passed; Codex sync preview and application succeeded; a second preview reported unchanged output. All nine source built-in rule hashes matched the pre-edit capture and generated built-ins were unchanged. The sync CLI advertises `--skip core` but rejects it; the supported provider-specific invocation with `--skip mcp --skip precommit` was previewed before use. Installation-owned CLI wording was not edited.

The focused Vault check initially exposed existing feature hygiene warnings and a stale feature index in addition to the fresh scaffold placeholders. This body replaces the new placeholders; unrelated historical documents were not rewritten. No full registry test, authority publication or runtime acceptance claim is made by this review.
