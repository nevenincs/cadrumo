---
tags:
  - '#adr'
  - '#website-repository-boundary'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:f6db3e843c8e4c929fe2c2fb4fd928817d09048ab275c9699da19cc2837c75d4'
related:
  - "[[2026-08-23-website-repository-boundary-research]]"
  - "[[2026-07-27-canonical-release-pipeline-adr]]"
  - "[[2026-07-21-ci-discipline-adr]]"
---
# `website-repository-boundary` adr: `marketing website belongs wholly to the marketing repository` | (**status:** `accepted`)

## Problem Statement

The Cadrumo marketing website was mistakenly treated as part of the product repository and its release lifecycle. Its implementation and operational surface have moved to the marketing repository, but accepted decisions, release documentation, and active comments still preserve obsolete product-side ownership. A binding repository boundary is required so code, automation, commands, documentation, and architecture records agree and cannot recouple website delivery to product releases. Grounding: `2026-08-23-website-repository-boundary-research`.

## Considerations

- The marketing repository already contains the complete website source and operational surface. Grounding: `2026-08-23-website-repository-boundary-research`, â€œThe website implementation and its operational surface have already moved as one unit.â€�
- The product repository retains product distributions and product-documentation publication, neither of which requires the marketing website. Grounding: `2026-08-23-website-repository-boundary-research`, â€œThe surviving runtime coupling is infrastructure partitioning, not release-pipeline coupling.â€�
- A shared delivery target does not justify shared source, command, CI, or release ownership. Grounding: `2026-08-23-website-repository-boundary-research`, â€œThe surviving runtime coupling is infrastructure partitioning, not release-pipeline coupling.â€�
- Two accepted ADRs retain valid product release and CI decisions alongside obsolete website clauses. Grounding: `2026-08-23-website-repository-boundary-research`, â€œAccepted decisions still contain obsolete product-repository website ownership.â€�
- Durable inverse enforcement is required in the product repository, but active workflow and command comments should describe the current invariant rather than migration history. Grounding: `2026-08-23-website-repository-boundary-research`, â€œOption 3.â€�

## Considered options

### Keep the website in the product repository

Rejected. This reverses the completed migration, restores a release-unrelated toolchain and CI lane, and creates conflicting ownership unless the marketing repository is dismantled. Grounding: `2026-08-23-website-repository-boundary-research`, â€œOption 1.â€�

### Keep website source in marketing but retain product-side commands or workflows

Rejected. Cross-repository dispatch, imports, or product-side website commands divide operational ownership and introduce permissions, revision, and failure coupling for a non-product artifact. Grounding: `2026-08-23-website-repository-boundary-research`, â€œOption 2.â€�

### Fully rehome the website and retain only product distributions and product documentation here

Accepted. The marketing team and repository own the website's source, dependencies, build, tests, CI, commands, publisher, deployment, verification, and recovery. The product repository owns product distributions, product release automation, and product-documentation publication only. Grounding: `2026-08-23-website-repository-boundary-research`, â€œOption 3.â€�

## Constraints

- Product release workflows, product CI, and product commands must not invoke, dispatch, import, build, test, publish, verify, or recover the marketing website.
- Product release documentation must not present website delivery as a prerequisite, gate, consequence, verification target, troubleshooting concern, or rollback responsibility.
- Product documentation publishing remains product-owned and must not be removed or conflated with marketing website publishing.
- Shared delivery infrastructure is a path-partitioning seam. It must remain protected by exclusions and delivery assertions without becoming release-pipeline coupling.
- The product repository retains inverse anti-regression gates that detect returned website ownership markers or a website CI lane.
- Active workflow, Just, and enforcement comments state durable present-tense constraints rather than migration history.
- Product application presentation boundaries named â€œfrontendâ€� are outside this decision.
- Stable portions of `canonical-release-pipeline` and `ci-discipline` remain authoritative. Only their website-specific ownership clauses are invalidated and narrowed here.

## Implementation

Reconcile the product repository to a strict negative ownership boundary. Remove remaining website commands, workflow behavior, release actions, documentation procedures, and operational descriptions. Preserve product distributions and independently triggered product-documentation publication.

Keep product-side anti-regression tests that assert the absence of website source ownership and a website CI lane. Express those gates as current invariants without recounting the migration.

Treat the marketing repository as the sole operational home for website source, dependency management, development, build, tests, CI, commands, publishing, deployment verification, and recovery. Retain no product-side compatibility shim or forwarding command.

Treat shared delivery infrastructure as a bounded path-partitioning seam. Marketing owns the site root while product documentation owns its reserved documentation path. Safety checks may protect that partition, but neither repository's release pipeline becomes a prerequisite or dispatcher for the other.

Amend `canonical-release-pipeline` and `ci-discipline` in the same reconciliation action. Remove or narrow only clauses that assign website publishing, commands, or CI classification to the product repository. Do not wholly supersede either ADR because their remaining decisions continue to govern.

Rewrite product release documentation around the actual product artifact and documentation lifecycle. State the external ownership boundary once, then omit website work from the procedure.

## Rationale

Full operational ownership is the only option that matches current implementation while preserving one accountable home for every website concern. It prevents product releases from acquiring cross-repository permissions, revision coordination, failure semantics, or gates for an artifact this repository does not own. Grounding: `2026-08-23-website-repository-boundary-research`, â€œOption 3.â€�

The shared infrastructure does not defeat this ownership model because its contract is path separation and survival checks, not coupled source trees or release orchestration. Grounding: `2026-08-23-website-repository-boundary-research`, â€œThe surviving runtime coupling is infrastructure partitioning, not release-pipeline coupling.â€�

Amending the two existing ADRs is preferable to superseding them: this decision corrects a bounded ownership mistake, while their other canonical release and CI decisions remain applicable. Supersession would incorrectly retire valid product architecture.

## Consequences

- The marketing team and repository are solely accountable for the website lifecycle.
- Product releases contain no website build, test, publication, verification, or rollback work.
- Product documentation remains product-owned and may publish independently as a downstream release consequence.
- Product CI and commands require no website toolchain or cross-repository orchestration.
- Inverse gates make website reintroduction an explicit architecture violation.
- Active automation and documentation describe current ownership without migration-era operational history.
- Shared infrastructure remains a coordination seam requiring safety assertions until a separate decision changes it.
- Future website source, commands, workflows, or release coupling in the product repository require a new architectural decision.
- `canonical-release-pipeline` and `ci-discipline` remain accepted after targeted amendment.
