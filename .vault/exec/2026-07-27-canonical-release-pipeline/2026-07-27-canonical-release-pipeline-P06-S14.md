---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S14'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

# Remove the CI-refusal guard from the docs publisher in the same change that binds the consequence workflow to the protected docs environment, gate: uv run --no-sync pytest dev/deploy/tests -q passes with the guard's absence asserted and the build path exercised under CI markers, deployment against the live stack is BLOCKED on OP-3 and flagged non-local

## Scope

- `dev/deploy/docs_static_site.py`
- `dev/deploy/frontend_static_site.py`
- `dev/deploy/tests/`

## Description

- Remove the documentation publisher's blanket refusal of every automated run.
- Require the delivery role identifier instead, so an automated publish must
  prove it is the environment-bound one.
- Export that identifier from the workflow under the name the publisher reads.
- Give the landing publisher its own unconditional refusal, no longer shared.
- Gate the transfer in both directions and pin the workflow half to the code
  half.

## Outcome

Landed under the commit subject `feat(deploy): bind the docs publish authority
to the delivery environment`, both halves in one commit as the Step requires.

The blanket refusal is gone. Publishing the site from automation is now a
supported authority rather than an accident, which is what makes documentation a
release consequence workable at all.

The property that refusal protected is not gone, and separating those two things
is the whole change. The hazard is specific to a shared self-hosted fleet: a
co-resident automated run may inherit an ambient cloud session, in which case it
never needs the federated role and the role's existence alone would not stop it.
So the publisher requires the delivery role identifier, which the protected
environment publishes to the sanctioned job alone.

The timing consequence is the reason this could land ahead of the operator
decision that provisions the role. Until that role exists the variable is absent
and every automated run is refused exactly as before, so the permission opens on
provisioning rather than on this commit. That is a runtime invariant rather than
a scheduling assumption, which is stronger than the commit-time coincidence the
decision record describes, because the role is an external act that can never
literally land in a commit.

The landing publisher is deliberately asymmetric. It has no workflow, no role
and no environment, so there is no automated identity for a conditional
permission to be granted to and its refusal stays absolute. It now carries its
own guard rather than sharing the documentation one, because sharing would have
silently extended the documentation site's new authority to a surface that was
never granted any.

Gate: the deploy suite passes at thirty-eight tests, up from twenty-eight.

Anti-tautology proof, run in both directions. Permitting every automated run
reds three tests; restoring the blanket refusal reds two. The build-path probe
drives the real publish entry point at a cloud executable that does not exist
and asserts on the command it emits, so an authorised run is observed reaching
the cloud call and an unprovisioned one is observed never attempting it.

## Notes

Deployment against the live stack was not attempted and is not possible from
here: it remains blocked on the operator decision that creates the identity
provider, the least-privilege role and the protected environment. This change is
verified locally only, and the workflow stays inert until that decision
completes.

The Step's atomicity requirement was partly satisfied before this Step began.
The environment binding itself landed with the preceding Step, which shipped the
workflow already declaring the protected environment. What remained to bind here
was the coupling that had no owner: the workflow exported the role identifier
under one name while nothing read it, so the surviving half of the atomic change
was making the publisher read it and correcting the workflow's own comment,
which asserted a blanket refusal this change removes.

The preceding Step deferred this work on the argument that removing the guard
before the role exists would strip a safety property for nothing. That argument
was correct about the blanket removal and is answered rather than overridden:
the refusal is conditioned on provisioning instead of deleted, so no automated
run gains any capability until the operator acts.

Two type-checker diagnostics remain in the deploy package. Both predate this
change, sit on lines it does not touch, and were confirmed present at the prior
commit; the module added here reports none.
