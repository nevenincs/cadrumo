---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:a19e79384a50cf3bbf53da30c066c6c33f775746d91a54f24314c856732b6201'
step_id: 'S13'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

# Author the docs consequence workflow triggered on release published and by dispatch, running on the self-hosted fleet, reading the deploy role from an environment-scoped variable with zero stored credentials, alerting on failure and never blocking the release, gate: a workflow conformance test pins the trigger set, runner labels, OIDC permissions, and the absence of secret literals and passes locally, live execution is BLOCKED on OP-3 and flagged non-local

## Scope

- `.github/workflows/docs-publish.yml`
- `dev/deploy/tests/`

## Description

- Author the delivery workflow, triggered after a release rather than during one.
- Refuse instructively before provisioning, as the first step.
- Federate an identity so no credential is stored.
- Assert the separation against the publication authority, not only this workflow.

## Outcome

Landed under the commit subject `feat(docs): deliver documentation downstream of
a release, never inside it`.

Documentation publication is a release consequence, never a gate. A strict
multi-root site build inside the publication path would let a documentation
defect strand a half-published release: the irreversible upload cannot be
unwound, so blocking on a rebuildable artefact would trade a recoverable problem
for an unrecoverable one. On failure this workflow alerts and stops, and its
conformance test forbids every verb that could reach back into the release.

The separation is asserted against the publication authority itself, because the
failure mode is publication acquiring a dependency on documentation rather than
the reverse.

Identity is federated with no stored credential, so there is no secret at rest
for a co-resident job on the shared runner fleet to read, and the protected
environment is the product boundary.

Gate: the deploy suite passes at twenty-eight tests.

Anti-tautology proof: building the current branch instead of the released commit
reds its test. Documentation must describe the release that triggered it.

## Notes

Deliberate deviation from the plan, which paired this Step with the removal of
the publisher continuous-integration refusal guard. That removal is only safe in
the same change that lands the deploy role, and the role is an operator act that
has not happened. Removing the guard now would strip a safety property in
exchange for nothing, since the workflow still could not authenticate. The
workflow therefore ships inert and says so: its first step refuses, names the
operator decision that unblocks it, and enumerates what to provision, before
checking anything out.
