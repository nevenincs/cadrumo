---
tags:
  - '#exec'
  - '#ledger-renta-pipeline'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-ledger-renta-pipeline-plan]]"
---



# `ledger-renta-pipeline` `phase-0` `step-1-pipeline-normalization`

Created the formal VaultSpec pipeline kickoff artifacts for the
ledger-to-Renta integration feature and removed the temporary draft
files used before the pipeline was established.

- Created: `.vault/adr/2026-05-08-ledger-renta-pipeline-adr.md`
- Created: `.vault/plan/2026-05-08-ledger-renta-pipeline-plan.md`
- Removed: `tmp/ledger-renta-rollout/2026-05-08-raw-brief.md`
- Removed: `tmp/ledger-renta-rollout/2026-05-08-rollout-kickoff.md`
- Created: `.vault/exec/2026-05-08-ledger-renta-pipeline/2026-05-08-ledger-renta-pipeline-phase0-step1.md`
- Created: `.vault/ledger-renta-pipeline.index.md`

## Description

Phase 0 normalized the feature into the VaultSpec pipeline.

The research artifact already existed and established the current
state of the live ledger backend, invoice linkage, category
proportionality substrate, calculation registry, Renta formula
surface, and missing persisted ledger-to-Renta path.

The ADR accepts the architecture decision that ledger-to-Renta
integration is a new pre-calculation observation and binding pipeline.
It keeps repository loading outside `calculate_registry_snapshot`,
uses the transaction catalogue as canonical classified ledger state
unless a later ADR changes that, and requires typed Renta observations
with provenance and legal/category grounding.

The plan defines the execution sequence: pipeline normalization,
modeller input inventory, contract decisions, deductibility model and
evaluator work, repository-backed aggregation, registry binding and
calculation integration, and legal hardening.

Temporary files under `tmp/ledger-renta-rollout` were removed after
their useful content was represented in formal `.vault` artifacts.

The feature index was generated with the VaultSpec CLI after the
initial feature check reported the missing-index warning.

## Tests

Validation commands run:

- `uv run vaultspec-core vault check features --feature ledger-renta-pipeline`
- `uv run vaultspec-core vault check frontmatter`
- `uv run vaultspec-core vault check body-links`
- `uv run vaultspec-core vault check links`
- `uv run vaultspec-core vault check schema`
- `uv run vaultspec-core vault check dangling`
- `uv run vaultspec-core vault check structure`

The first feature check exited successfully with the expected warning
that the new feature had no generated feature index. The index was then
generated with `uv run vaultspec-core vault feature index -f ledger-renta-pipeline`.
The final feature check exited cleanly for `ledger-renta-pipeline`.

Frontmatter, body-link, and wiki-link checks exited successfully. The
schema, dangling, and structure checks still report pre-existing
vault-wide issues in unrelated documents and existing index files; no
new ledger-renta-specific failure was identified in those outputs.

No feature code was implemented in Phase 0, so no unit or integration
test run was applicable for this step.
