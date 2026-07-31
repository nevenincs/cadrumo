---
tags:
  - '#plan'
  - '#scoop-runner-topology'
date: '2026-07-25'
modified: '2026-07-30'
body_hash: 'sha256:b28635c71353aca09deb9c1d8a7255966f8b65e70e4bf5830388130a1bef4396'
tier: L1
related:
  - '[[2026-07-22-scoop-runner-topology-adr]]'
  - '[[2026-07-17-post-release-distribution-plan]]'
---

<!-- RETIRED: S01, S02, S03 -->

# `scoop-runner-topology` plan

- [x] `S05` - Adapt the Scoop acquisition lane to the ADR-ruled native execution, replacing the docker Windows-container preflight and the Container-mode harness invocation with a native Host-mode invocation pinned to the windows-scoop runner label, a preflight asserting AMD64 plus a resolvable Scoop in the lane user's profile, and a per-run Scoop profile reset that keeps acquisitions independent, and update the structural gate to pin the native shape; `.github/workflows/packaging-scoop.yml, dev/packaging/tests/test_scoop_workflow.py, dev/packaging/smoke_scoop.ps1`.
- [x] `S04` - Record an explicit unaffected-and-why reconciliation against the account-distribution-standard ruling, because this record governs which runner executes the Scoop evidence lane while that record governs where Scoop manifests live, and a reader finding two Scoop decisions with no stated relationship must not have to re-derive the orthogonality; `.vault/adr/2026-07-22-scoop-runner-topology-adr.md`.
## Description

Move the Scoop evidence lane onto the execution host the governing ruling
chose, and record honestly what remains a person's job.

On 2026-07-30, 3 open rows (S01, S02, S03) were removed from this plan and
migrated to 2026-07-30-open-work-consolidation-plan, which now carries them as
one ordered flow authorised by 2026-07-30-open-work-consolidation-adr. These
rows were migrated, not delivered: the reduced row count reflects a change of
carrier, not a narrowing of scope, and none of the underlying blockers or
preconditions described below changed as part of this migration.

The lane mints one distribution-evidence row by really installing the tested
cohort through Scoop, exercising the CLI and MCP oracles against it, updating,
uninstalling, and reinstalling to prove persistence survives each, then
removing everything it introduced. Nothing about that needs a container: Scoop
is user-scope and needs no admin. What it does need is a Windows user profile
that is not shared with interactive work, on a machine the fleet already owns.

What the two host rows actually require, measured on the workstation on
2026-07-28 rather than inferred.

The existing Windows runner for this repository is not a shortcut. It runs
interactively under the operator's own account, and that account is a member of
Administrators, so relabelling it would be refused by the lane's own privilege
preflight. No dedicated non-admin user exists yet. Creating one needs
administrator rights, which an agent session on this box does not have and
should not take.

The provisioning is three moves. Create a standard local user for the lane and
do not add it to Administrators. Sign in as that user once so the profile
materialises, and install Scoop into it, which is itself a no-admin user-scope
install. Then register a runner against this repository under that user with
the lane's label, minting the registration token from the repository's own
Actions API. None of that needs a restart: registering a runner is an unzip and
a service registration, which is why the fleet's existing runners were stood up
without one.

Whether the runner is registered as a service under that account or run
interactively in that user's session is the operator's call. The lane does not
inspect how the runner was installed. It reads the identity it actually runs
as, so a wrong choice surfaces as a named refusal on the first dispatch rather
than as silently privileged evidence.

The Windows Sandbox row is unrelated to all of the above and serves a different
proof. Its feature state was first recorded here as unreadable without
elevation, which was wrong: the optional-feature inventory is readable over WMI
from an ordinary session, and it reports `Containers-DisposableClientVM`
disabled with no sandbox executable present, confirming the earlier operator
finding rather than leaving it unverified.

Enabling it needs administrator rights. Whether it also needs a restart is not
settled here. The feature it layers on is already installed and running, since
the virtual-machine platform, the hypervisor platform, and Hyper-V are all
enabled on this host, so a restart is not the foregone conclusion it would be
on a bare machine. The enable call reports whether a restart is pending in its
own result and takes a flag to suppress one, so the operator should read that
answer rather than schedule a reboot in advance. This matters because a restart
here is not cheap: it takes down the CI runners and every agent session on the
box.

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

A second precondition on the acquisition re-run was measured on 2026-07-28 and
is worth knowing before anyone provisions the host expecting the row to follow.
The lane refuses a source run whose conclusion is not success, and there is no
successful packaging-smoke run to name: the recent history is failures, and the
one in flight at the time of measurement already carried a failed wheel leg.

So the two open host rows and this row are not a chain of three. Provisioning
the runner clears the host precondition and nothing else; the source-run
precondition is cleared by the packaging campaign, which is where that work is
tracked. Dispatching this row before a green smoke run exists produces a
refusal at the source-identity gate, not a green acquisition.

The cause of that missing green smoke run was traced so whoever picks it up
does not repeat the search. The Linux wheel leg fails because the packaging
campaign's `dev` lane exits 127 on a `pyright --version` call inside its
freshly built lane venv, which is a missing executable rather than a product
failure, and the same exit-127 class was already recorded against the macOS
oracle leg. Every other lane in that run passed, including both Docker lanes
and all three immutable-cohort oracle legs.

That is the packaging campaign's surface, not this one's, and it is left there
deliberately: repairing a lane venv on a shared runner host is an
infrastructure change with a blast radius well outside a runner-topology
decision. It is named here only because it is the precondition this plan's
acquisition row actually waits on.

That exit-127 was traced further, on the runner itself, so the handoff carries
facts rather than a symptom. The `pyright` console script is a thin Python
wrapper that runs the real analyser as JavaScript, so it needs both a Node
binary and the analyser's own npm package. On the Linux runner container:
neither `node` nor `npm` is on PATH, though the runner image ships working Node
20 and Node 24 under its externals directory, and the wrapper's own bootstrap
cache already holds a working Node 26. The npm registry and PyPI both answer
HTTP 200 from inside the container, so egress is not blocked. What is missing is
the analyser's npm package, which has never landed in that cache.

The wrapper prefers a Node found on PATH and falls back to its bootstrap cache,
and that cached Node runs, so the failure is not simply an absent interpreter.
Why the package never installs is not pinned, and pinning it means creating a
virtual environment inside a peer campaign's live runner to reproduce, which is
where this stops. The lane's own workspace from the failed run has already been
cleaned up, so the artefact is gone.

Worth noting for whoever takes it: nothing here is a code regression. The
analyser entered the dev command surface and the dependency group long ago, so
the change is environmental, and the cheapest thing to try first is putting the
runner image's existing Node on PATH for that lane.

## Context

Accepted ADR carrying no plan. Rules which runner executes the Scoop evidence lane, orthogonal to where Scoop manifests live, which the account-distribution-standard ADR settles.

The plan as first authored carried a row directing the operator to switch the shared Docker daemon into Windows-container mode. That is the option the governing ADR considered and rejected, because a mode switch on the single fleet daemon tears down the two standing Linux runners on every Scoop run. The row has been reconciled to the decision actually in force: a native Windows self-hosted runner under a dedicated non-admin local user, labelled for the Scoop lane, with the Docker daemon left permanently in Linux-container mode.

The existing docker-mode preflight is therefore superseded rather than weakened. The native lane replaces it with an equally fail-closed preflight over the surface the native execution actually depends on: an AMD64 host and a resolvable Scoop in the lane user's profile. Adapting the workflow to that shape is tracked as its own row, because until it lands the lane refuses at a preflight guarding a topology the ADR has retired, and no amount of operator provisioning can turn the row green.
