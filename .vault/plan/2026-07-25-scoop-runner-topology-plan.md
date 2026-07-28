---
tags:
  - '#plan'
  - '#scoop-runner-topology'
date: '2026-07-25'
modified: '2026-07-28'
tier: L1
related:
  - '[[2026-07-22-scoop-runner-topology-adr]]'
  - '[[2026-07-17-post-release-distribution-plan]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `scoop-runner-topology` plan

- [ ] `S01` - Provision a native Windows self-hosted GitHub Actions runner on the workstation under a dedicated non-admin local user with Scoop pre-installed in that user's profile and the runner labelled windows-scoop, because the governing ADR rejected the shared-daemon Windows-container mode switch this row previously named and rules instead that the Docker daemon stays permanently in Linux-container mode so the standing Linux runners are never stopped, OPERATOR-GATED as a host action; `operator action, Windows workstation runner service and dedicated local user`.
- [x] `S05` - Adapt the Scoop acquisition lane to the ADR-ruled native execution, replacing the docker Windows-container preflight and the Container-mode harness invocation with a native Host-mode invocation pinned to the windows-scoop runner label, a preflight asserting AMD64 plus a resolvable Scoop in the lane user's profile, and a per-run Scoop profile reset that keeps acquisitions independent, and update the structural gate to pin the native shape; `.github/workflows/packaging-scoop.yml, dev/packaging/tests/test_scoop_workflow.py, dev/packaging/smoke_scoop.ps1`.
- [ ] `S02` - Re-run the clean Scoop acquisition gate on the declared Windows release row once the native windows-scoop execution host from S01 exists and the native lane from S05 has landed, noting that this row stages its own local file-URI bucket from the verified cohort and therefore does not wait on a published manifest, since the latest run 29895961436 refused at the now-superseded docker-mode preflight and no clean acquisition evidence exists; `.github/workflows/packaging-scoop.yml`.
- [ ] `S03` - Enable Windows Sandbox on the Windows host so the install-from-bucket smoke can execute CLI, MCP, update, and persistence behaviour, OPERATOR-GATED as a host action; `operator action, Windows host feature`.
- [x] `S04` - Record an explicit unaffected-and-why reconciliation against the account-distribution-standard ruling, because this record governs which runner executes the Scoop evidence lane while that record governs where Scoop manifests live, and a reader finding two Scoop decisions with no stated relationship must not have to re-derive the orthogonality; `.vault/adr/2026-07-22-scoop-runner-topology-adr.md`.
## Description

Move the Scoop evidence lane onto the execution host the governing ruling
chose, and record honestly what remains a person's job.

The lane mints one distribution-evidence row by really installing the tested
cohort through Scoop, exercising the CLI and MCP oracles against it, updating,
uninstalling, and reinstalling to prove persistence survives each, then
removing everything it introduced. Nothing about that needs a container: Scoop
is user-scope and needs no admin. What it does need is a Windows user profile
that is not shared with interactive work, on a machine the fleet already owns.

## Steps

## Parallelization

The two operator host actions are independent of each other and of everything
else. Provisioning the runner needs a new local user and a service install.
Enabling Windows Sandbox needs administrator rights and a reboot, and serves a
different proof entirely, so neither waits on the other.

The lane adaptation is independent of both and lands first, because until it
does the workflow refuses at a gate no host action can satisfy.

The acquisition re-run is the only strictly sequential row: it needs the
adapted lane and the provisioned runner, in that order.

## Verification

The lane adaptation is verified by its structural gate, which pins the native
runner label, the native preflight including its non-elevation refusal, the
Host-mode invocation, the full staged harness module set, and the evidence
binding check ordered ahead of the emitter. It also carries negative pins
against the container invocation, so a silent revert reddens the gate rather
than quietly stranding the row. Each of those pins was confirmed to fail when
the corresponding workflow clause is mutated away, and the evidence binding
check was separately executed against a synthetic evidence shape to confirm it
accepts an honest native run and refuses each corruption by name.

The runner provisioning is verified by the lane itself rather than by
inspection: a runner installed under an elevated account, or one whose user has
no Scoop profile, refuses at the preflight with a message naming the fix.

The row is green only when a dispatched acquisition run publishes a
`scoop-windows-x86-64` record onto its own sealed evidence draft. No other
signal counts, and no locally minted or hand-written row is admissible in its
place.

One consequence of pinning the runner label is worth knowing before the host
exists. Previously a dispatch failed within seconds at the docker-mode
preflight. Now, with no runner carrying the label, a dispatch instead waits for
a matching runner and is bounded only by the job timeout. That is the honest
behaviour, since the job genuinely cannot run anywhere else, and the queue
state names the labels it is waiting for, but it reads as a hang rather than a
refusal to anyone who dispatches the lane before provisioning the host.

## Context

Accepted ADR carrying no plan. Rules which runner executes the Scoop evidence lane, orthogonal to where Scoop manifests live, which the account-distribution-standard ADR settles.

The plan as first authored carried a row directing the operator to switch the shared Docker daemon into Windows-container mode. That is the option the governing ADR considered and rejected, because a mode switch on the single fleet daemon tears down the two standing Linux runners on every Scoop run. The row has been reconciled to the decision actually in force: a native Windows self-hosted runner under a dedicated non-admin local user, labelled for the Scoop lane, with the Docker daemon left permanently in Linux-container mode.

The existing docker-mode preflight is therefore superseded rather than weakened. The native lane replaces it with an equally fail-closed preflight over the surface the native execution actually depends on: an AMD64 host and a resolvable Scoop in the lane user's profile. Adapting the workflow to that shape is tracked as its own row, because until it lands the lane refuses at a preflight guarding a topology the ADR has retired, and no amount of operator provisioning can turn the row green.
