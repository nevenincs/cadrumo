---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:244a2c039921a4b54005a254afa2fc4b89c70561fb0c23f9fe15a2b72b4cbed2'
step_id: 'S134'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---




# implement the concrete connected-proof authority from live source enrollment, supported workflow catalogues, repository evidence digests, and encrypted revision reads

## Scope

- `src/cadrumo/application/registry`

## Description

- Define the deterministic live source-kind and resolver ownership catalogue.
- Compose exact enrolled source ownership with reconciled calculation workflows.
- Verify encrypted revisions by exact revision id and unique persisted provenance identity.
- Refuse missing, ambiguous, drifted, deferred, or reserved source claims.
- Hash executable evidence through an injected repository-root containment policy.
- Publish the authority and dependency ports through the registry application facade.

## Outcome

Connected census admission now has a concrete application authority backed by
live policy inputs, encrypted calculation-revision reads, reviewed operator
workflows, and deterministic repository evidence. No proof boolean substitutes
for those reads, and no adapter, entrypoint, private sibling module, ambient
repository root, or process-global catalogue participates in the decision.

## Notes

Comprehensive encrypted repository behavior and mutation coverage remains owned
by the following test step. This step includes narrow contract coverage for
catalogue ordering and repository digest containment. The repository-wide
import-hygiene scan remains blocked by the unrelated accepted-disposition gap
for `cadrumo.adapters.inbound.tui._recovery_words_screen`, observed during the
immediately preceding prerequisite step.
