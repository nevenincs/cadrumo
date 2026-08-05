---
tags:
  - '#audit'
  - '#ci-runner-standardization'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:a052e0c602fc95d4011d761c2c5090ee9fec2cc85f90d969549efc502cf46daf'
related: []
---

# `ci-runner-standardization` audit: `Self-hosted runner inventory and standardization proposal`

## Scope

Every self-hosted GitHub Actions runner registration physically resident on the shared
Windows/WSL build host, enumerated across all four hosting mechanisms — Windows
services, Windows scheduled tasks, WSL systemd units, and Docker containers — and
reconciled against the live GitHub registration state for the four repositories that
register runners here. Runners are identified by role rather than by machine name,
following the convention the runners README already sets and the privacy gate enforces.

The first pass was investigation and proposal only. A later pass, on explicit operator
authority, actioned the findings; the corrections appended to the findings log below
record where the first pass was wrong. Nothing was started, stopped, or reconfigured
without that authority, and credential material was never read or printed.

The trigger was an operator observation that runner directory naming is inconsistent
across projects. Naming turned out to be the least consequential finding. Four
registrations were visible as directories on `C:\` and only two as Windows services;
the asymmetry was the thread that led to the hazards below.

## Findings

### complete-inventory | medium | Nine registrations across four hosting mechanisms; only two were visible as Windows services

Enumerating only Windows services understates the resident runner population by more
than a factor of four. The complete set, all bound to repositories under the
`nevenincs` account:

Windows services (2, both running): `vaultspec-core-win-x64` for the `vaultspec-core`
repository out of `C:\actions-runner-vaultspec-core`, and `vaultspec-rag-gpu-win` for
`vaultspec-rag` out of `C:\actions-runner-vaultspec-rag`.

WSL Ubuntu systemd units (2, both active): the dashboard WSL registration for
`vaultspec-dashboard` out of `~/vs-runner`, and `vaultspec-rag-linux` for
`vaultspec-rag` out of `~/gh-runner-vsrag`.

Docker containers (3, all up): `cadrumo-runner-linux-2`, carrying this repository's
sole Linux X64 registration, plus `dev-runner-vaultspec-core` and
`build-runner-vaultspec-core`, the latter two managed by a Compose project rooted in a
separate development-runner worktree.

Windows scheduled tasks at logon (2 enabled but not currently serving):
the cadrumo Windows runner task launching `C:\actions-runner\run.cmd` for this
repository, and `VaultspecRunnerWin` launching `C:\actions-runner-vs\run-vs.cmd` for
`vaultspec-dashboard`. A third task, `VaultspecRunnerWsl`, is enabled and duplicates a
systemd-managed registration (see below). A fourth, `CadrumoActionsRunner`, is
disabled and is a superseded duplicate of the first.

Seven runners are online on this box right now. Two more start automatically at the
next interactive logon, for a ceiling of nine.

### windows-lane-unschedulable | critical | This repository has no online Windows runner while eight workflow jobs target one

The Windows build-host registration reports `status=offline` at the GitHub API. Its
launcher is a logon-triggered scheduled task whose last recorded exit was a failure,
and its diagnostic log stopped advancing on 4 August. Its working tree and diagnostics
prove it served jobs until then, so this is a live registration that has fallen over,
not an abandoned one.

Meanwhile this repository's workflows request `[self-hosted, Windows, X64]` in the
Claude packaging lane, the quick packaging lane, and twice in the packaging smoke
lane. With no online runner carrying that label set, those jobs queue indefinitely
rather than failing fast — the failure mode presents as a hung workflow, not a red
one. The same pattern holds for `vaultspec-dashboard`, whose Windows registration
is also offline with a terminated-process exit code.

### scoop-label-unsatisfiable | critical | The Scoop packaging lane requests a label no runner anywhere carries

The Scoop packaging workflow requests `[self-hosted, Windows, X64, windows-scoop]`.
Querying every runner registered to this repository for the `windows-scoop` label
returns nothing. No runner on this machine or any other carries it. That lane has
never been schedulable and cannot become schedulable by bringing the Windows runner
back up, because the offline Windows registration carries only
`[self-hosted, Windows, X64]`.

This is distinct from the finding above and survives its fix. The control plane
document classifies the Scoop lane as dispatch-only, which is likely why the gap went
unnoticed: a lane nobody dispatches never reveals that it cannot be dispatched.

### concurrency-denominator-wrong | high | Worker sizing is derived from three co-resident runners; seven are online

The repository pins `-n 8` for pytest across at least six workflows and the justfile,
each carrying a comment deriving the figure as twenty-four logical CPUs divided by
three co-resident runners. The control plane document states the same premise
explicitly: the Windows/WSL build host carries the Windows runner plus two Linux
container runners.

That denominator counts only this repository's own runners. It does not count the two
Windows services, the two WSL systemd units, or the two additional Compose-managed
containers belonging to the other three repositories, all of which are resident on the
same twenty-four logical CPUs. The true concurrent-runner count is seven online, nine
at ceiling.

If several lanes run at once the box is oversubscribed by roughly a factor of two to
three against the sizing the comments claim to have computed. The pin itself may still
be a reasonable operational compromise — but the stated derivation is false, and a
future agent recomputing from the documented premise will reach a worse number with
apparent justification. The premise is the defect, independently of the value.

### wsl-runner-double-start | high | An enabled scheduled task launches a registration systemd already owns

The scheduled task `VaultspecRunnerWsl` is enabled with a logon trigger and executes
the run script in the WSL `~/vs-runner` directory. A systemd unit inside the same WSL
distribution already runs that identical directory and holds the live registration.

At the next interactive logon the task will attempt to start a second listener against
a registration that is already connected. The two are not coordinated. The task last
completed successfully in late July, before systemd took ownership, so the conflict
window is recent and has probably not yet been hit.

### cross-repo-misrouting-impossible | low | Label collisions exist but cannot cause cross-project mis-routing

Three registrations share effectively the same label set, differing only in ordering:
this repository's Windows runner, the `vaultspec-core` Windows runner, and the
`vaultspec-dashboard` Windows runner all present `self-hosted`, `Windows`, `X64`. On a
shared runner pool this would be a genuine mis-routing hazard.

It is not one here. The account `nevenincs` is a user account, not an organisation —
the organisation-runner endpoint returns not-found — so no organisation-level or
shared runner group can exist. Every registration is repository-scoped, and a
repository-scoped runner is only ever offered jobs from its own repository. The
label overlap is therefore cosmetic. This finding is recorded to close the question
rather than to raise it, because label overlap is the first thing a reviewer will
suspect and the reasoning that dismisses it is not obvious.

### no-shared-work-roots | low | No two registrations share a working directory

Each registration owns a distinct work root: the four Windows installations each keep
their own `_work` beside their runner directory, the two WSL installations keep theirs
under their respective home directories, and the containerised runners work inside
their own filesystems or a dedicated volume. The Compose-managed `vaultspec-core`
runners bind a worktree root belonging to that project only. Nothing binds this
repository's worktree root. There is no corruption hazard from a shared work root.

Two registrations do share cache roots by deliberate configuration — a compiler cache,
a package cache, and a dependency cache under a shared CI directory on each of Windows
and WSL. These tools are designed for concurrent access and this is not reported as a
hazard, but it is a coupling worth knowing about when reasoning about cache poisoning.

### provisioning-source-divergence | medium | The container entrypoint on disk differs from the one actually running

A directory in WSL holds a single provisioning script and nothing else — no
registration, no credentials, no diagnostics, no work tree. It is not bound into any
container. It reads as the source copy of the entrypoint for this repository's Linux
container runner.

It has diverged from the copy that actually runs: the two differ by checksum, and the
on-disk copy carries a block of provisioning logic placed after the process-replacing
exec that starts the runner, so that block is unreachable and has never executed. The
live copy does not contain it, and the tool that block would install is present in the
container by other means. The on-disk copy also carries an empty credential
placeholder; the live copy contains no credential argument at all. No credential
material is present in either.

The practical consequence is that the only on-disk record of how this repository's
Linux runner was provisioned is stale and contains dead code. It is not tracked in any
repository. If the container's volume is lost, this script is what someone would reach
for, and it would not reproduce the runner that was actually running.

### naming-inconsistency | low | Four naming axes vary independently, and one name asserts the wrong hosting mechanism

Directory naming: two directories carry the product name in full
(`actions-runner-vaultspec-core`, `actions-runner-vaultspec-rag`), one carries an
opaque abbreviation (`actions-runner-vs`, which is `vaultspec-dashboard`), and one
carries no product name at all (`actions-runner`, which is this repository). The
operator's observation is confirmed: the majority convention embeds the product name
and this repository is the principal deviation, with the abbreviated one a close
second.

Runner naming: `vaultspec-core` and `vaultspec-rag` lead with the product
(`vaultspec-core-win-x64`, `vaultspec-rag-linux`). This repository and
`vaultspec-dashboard` instead lead with the build host's machine name, appending the
platform and, for the dashboard, a project suffix. The machine-led form loses the
project when runners are listed per-repository, which is the only way they are ever
listed — and it embeds an operator-identifying host name in a field that is echoed
into public workflow logs.

Most significantly, this repository's Linux runner carries `wsl` in its registered
name while it is a Docker container, not a WSL runner. The name asserts a hosting
mechanism it does not use. That is what made this runner hard to locate: searching WSL
for it finds nothing.

### CORRECTION-provisioning-is-tracked | medium | The provisioning-source finding above was wrong; it is tracked and documented

Retracting the substance of `provisioning-source-divergence`. That finding claimed the
provisioning script "is not tracked in any repository". It is. The repository carries
`dev/runners/runner-entry-linux.sh` plus a long `dev/runners/README.md` that documents
the container topology, the entrypoint-in-the-volume rule, the exit-127 outage that
taught it, the tool-durability rule, and the restart discipline.

Diffing the tracked script against the entrypoint actually running inside the container
shows they differ in **two comment lines only** — the live copy substitutes the instance
name where the tracked copy carries a `<n>` placeholder. Executable content is
identical. There is no functional drift, and the tracked source would faithfully rebuild
the running runner.

The original finding was reached by searching the filesystem, the Docker state, and the
GitHub API, and never searching the repository's own `dev/` tree. That is a
methodological failure, not a close call: the mandated discovery sequence is to search
by meaning first, and a search for "runner provisioning" would have returned the README
immediately. The stale WSL copy is real and is still superseded residue — but it is
superseded *by a tracked successor*, which makes it ordinary leftovers rather than the
only surviving record of anything.

### CORRECTION-windows-service-absence-is-by-design | low | The missing Windows service is documented intent, not an anomaly

The inventory treated the absence of an `actions.runner.*` service for the Windows
runner as part of the asymmetry to be explained. The README already explains it: that
runner deliberately runs interactively as a console-session listener rather than as a
service, and the document states plainly that there is no `.service` marker and no
service to restart, that the hook takes effect on the next listener start, and that
killing the listener does not auto-resume it.

That also supplies the mechanism behind the offline state: a console-session runner
dies with its session, and the logon-triggered scheduled task exists precisely to
relaunch it. The runner being down is still a live problem — but it is a known-fragile
hosting choice behaving as documented, not an unexplained failure.

### CORRECTION-scoop-gap-is-tracked-and-operator-gated | high | The Scoop label gap is a known open row, and BOTH proposed fixes are wrong

The `scoop-label-unsatisfiable` finding stands on the facts but was wrong to imply the
gap was unnoticed. It is tracked as an open row in the open-work consolidation plan,
which already states in terms that no such label exists on the fleet today and marks
the row OPERATOR-GATED as a host act. A second row in the same plan names the runner
inventory exposing that label as the verification condition.

More importantly, both remedies proposed in this audit's own recommendations are wrong,
and one is actively destructive:

Removing the label from the workflow contradicts an accepted ADR that rules the Scoop
lane must run natively on a dedicated runner, and would break a structural test that
hard-asserts the exact four-element label list.

Adding the label to the existing Windows registration is worse. The ADR requires a
runner under a **dedicated non-admin local user**, with Scoop installing into *that
user's* profile, and the lane resets that profile between runs. The existing Windows
runner runs as the interactive operator account. Labelling it would schedule the lane
onto a runner that violates the ADR's isolation constraint, and the lane's
reset-between-runs step would then wipe the Scoop profile of the operator's own
account. The correct state is the current one: the lane stays unschedulable until the
operator provisions the dedicated user and runner.

### linux-capacity-halved | high | One of the two documented Linux container runners no longer exists

Both the runners README and the CI control plane document **two** Linux X64 container
runners, and the README's restart procedure explicitly warns never to take both down at
once because CI and smoke depend on the pair.

Only one exists. The second container is absent entirely — not stopped, absent — and
its GitHub registration is gone with it, leaving a single online Linux X64 runner for
this repository. Its state volume survives, orphaned, holding credentials for a
registration that no longer exists.

The README supplies the likely mechanism against itself: it warns that the cleanup hook
runs a container prune on every job completion, so a stopped container is reaped by the
next job finishing anywhere on the host. A container that stopped for any reason would
be removed before anyone noticed, and nothing would announce it.

This compounds the Windows outage rather than sitting beside it. More than thirty jobs
across this repository's workflows target `[self-hosted, Linux, X64]`. They now all
queue through one runner, so concurrent Linux work serialises where the documented
topology assumed it would not. That is a capacity halving that presents as slowness
rather than failure, which is why it survived undetected.

### CORRECTION-this-audit-leaked-the-host-name | high | The first commit of this audit put an operator-identifying host name into a public repository

The initial version of this document named the build host directly, nine times. The
repository is public, and `dev/quality/tests/test_doc_privacy.py` bans that token
tree-wide as leaked machine metadata — the runners README states the rule explicitly and
identifies runners by role for exactly this reason.

The gate caught it, but only because a later phase ran it; the audit's own commit went
in without running it first. The commit is local and has not reached the remote, so the
exposure is contained, but the token is in local history and cannot be removed by any
action permitted here — history rewriting is categorically forbidden in this shared
worktree, and the commit sits behind peer commits in the unpushed range. The tracked
content is now scrubbed to role-based identification; whether the local history needs
attention before any push is an operator decision, not one this audit can take.

The generalisable lesson is narrow and worth stating: an audit that inventories
infrastructure will naturally quote machine names, which is precisely the class of
string a public repository must not carry. Enumerating hosts and writing about them are
different acts with different disclosure rules, and the gate that knows this must be run
before the commit, not after.

### naming-must-not-embed-the-host | medium | The convention proposal needs a privacy constraint, not only a consistency one

The naming finding treated machine-led runner names as a discoverability problem. The
privacy gate shows they are also a disclosure problem. A runner name is echoed into
workflow logs, job summaries, and the API responses any collaborator can read, so a
machine-led name publishes the build host's name every time a job runs.

That converts the naming recommendation from a matter of taste into one with a stated
constraint behind it: the product-led convention the majority already follows is not
merely tidier, it is the only one of the two that keeps an operator-identifying token
out of public surfaces. This strengthens the case for renaming the machine-led
registrations, though it does not change the cost — a rename is still a
deregister/re-register cycle and still the operator's call.

## Recommendations

Ranked by consequence. The first three cause failures; the rest cause confusion.

Restore this repository's Windows runner and establish why it exits. Its scheduled
task records a failure exit and its diagnostics stopped advancing on 4 August. Until
it is back, four packaging jobs queue rather than run. Investigate the exit before
restarting, so the restart is a fix rather than a reset — the same class of failure
has recurred on this box before. Applies equally to the `vaultspec-dashboard` Windows
runner, which is that project's call.

Reconcile the Scoop lane's label against reality. Either add `windows-scoop` to this
repository's Windows registration — which is a deregister and re-register cycle, and
therefore downtime for that runner and the operator's decision — or amend the workflow
to request the label set a runner actually carries. The second is non-disruptive and
should be preferred unless the label is meant to pin a specially provisioned machine.

Correct the co-residency premise wherever the `-n 8` derivation is stated. The value
may well stand; the stated reasoning does not, because it counts three co-resident
runners where seven are online. Fix the control plane document first, since the
workflow comments cite it, then sweep the comments. Whether the pin should change is a
separate measurement question and should not be answered by assertion.

Disable the redundant WSL scheduled task before the next interactive logon, so the
systemd unit is the single owner of that registration. This is the one item where
waiting has a cost: the conflict fires on logon. It is a task-level change on a
`vaultspec-dashboard` surface, so the operator or that project's owner should make it.

Bring the container entrypoint under version control in the repository it provisions,
delete the unreachable block, and reconcile it with the copy actually running. Do not
delete the stale directory — it is the only surviving record of the provisioning, and
"superseded" is not the same as "reproducible". Retire it only once a tracked
equivalent exists and has been shown to rebuild the runner.

Adopt the majority naming convention rather than inventing one. The `vaultspec-core`
and `vaultspec-rag` registrations already agree on a shape and are the pattern to
generalise: the directory is `actions-runner-<product>`, the runner name is
`<product>-<platform>[-<variant>]`, the service name follows the runner name as the
tooling already derives it, and labels stay the platform triple plus a variant label
only where a workflow genuinely selects on it. Under that convention this repository's
runners become `actions-runner-cadrumo` with runner names `cadrumo-win-x64` and
`cadrumo-linux-x64`, and `vaultspec-dashboard` moves off the `-vs` abbreviation.

Weigh that renaming against its cost honestly. A runner name is fixed at registration,
so every rename is a deregister and re-register cycle — CI downtime for that project,
a new agent identity, and loss of that runner's job history. Three of the nine
registrations conform already. The naming problem causes confusion, not failure, and
the directory rename can be done independently of the runner rename at far lower cost.
A defensible middle path is to rename directories now, correct only the one name that
actively misleads about its hosting mechanism, and let the remaining runner names
converge naturally the next time each is re-registered for an unrelated reason.

Whether to accept that convention as binding is a decision this audit deliberately
does not take. If the operator adopts it, it warrants a follow-on ADR fixing the
naming shape, the label policy, and the hosting-mechanism-per-platform choice, since
those bind every future runner added to this box.

Finally, treat the mechanism inventory itself as the durable lesson. This box hosts
runners under four different mechanisms, and the two that are hardest to find — a
Docker container whose name claims it is a WSL runner, and logon-triggered scheduled
tasks — are exactly the two that were mis-modelled. Any future question of the form
"where does this project's CI actually run" must enumerate all four mechanisms.
