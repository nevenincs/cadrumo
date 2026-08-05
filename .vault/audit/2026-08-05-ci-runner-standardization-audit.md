---
tags:
  - '#audit'
  - '#ci-runner-standardization'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:210dc683477c5a88e10536520ddc321c2eeeba85fd599caa9d7dd28823d53f2e'
related: []
---

# `ci-runner-standardization` audit: `Self-hosted runner inventory and standardization proposal`

## Scope

Every self-hosted GitHub Actions runner registration physically resident on the
`gw-workstation` development box, enumerated across all four hosting mechanisms —
Windows services, Windows scheduled tasks, WSL systemd units, and Docker containers —
and reconciled against the live GitHub registration state for the four repositories
that register runners here. Investigation and proposal only; nothing was started,
stopped, reconfigured, or deleted. Credential material was never read or printed.

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

WSL Ubuntu systemd units (2, both active): `gw-workstation-wsl-vaultspec` for
`vaultspec-dashboard` out of `~/vs-runner`, and `vaultspec-rag-linux` for
`vaultspec-rag` out of `~/gh-runner-vsrag`.

Docker containers (3, all up): `cadrumo-runner-linux-2` registered as
`gw-workstation-wsl-2` against this repository, plus `dev-runner-vaultspec-core` and
`build-runner-vaultspec-core`, the latter two managed by a Compose project rooted in a
separate development-runner worktree.

Windows scheduled tasks at logon (2 enabled but not currently serving):
`cadrumo-runner-gw-workstation-win` launching `C:\actions-runner\run.cmd` for this
repository, and `VaultspecRunnerWin` launching `C:\actions-runner-vs\run-vs.cmd` for
`vaultspec-dashboard`. A third task, `VaultspecRunnerWsl`, is enabled and duplicates a
systemd-managed registration (see below). A fourth, `CadrumoActionsRunner`, is
disabled and is a superseded duplicate of the first.

Seven runners are online on this box right now. Two more start automatically at the
next interactive logon, for a ceiling of nine.

### windows-lane-unschedulable | critical | This repository has no online Windows runner while eight workflow jobs target one

The registration `gw-workstation-win` reports `status=offline` at the GitHub API. Its
launcher is a logon-triggered scheduled task whose last recorded exit was a failure,
and its diagnostic log stopped advancing on 4 August. Its working tree and diagnostics
prove it served jobs until then, so this is a live registration that has fallen over,
not an abandoned one.

Meanwhile this repository's workflows request `[self-hosted, Windows, X64]` in the
Claude packaging lane, the quick packaging lane, and twice in the packaging smoke
lane. With no online runner carrying that label set, those jobs queue indefinitely
rather than failing fast — the failure mode presents as a hung workflow, not a red
one. The same pattern holds for `vaultspec-dashboard`, whose Windows registration
`gw-workstation-win-vaultspec` is also offline with a terminated-process exit code.

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
`vaultspec-dashboard` lead with the machine (`gw-workstation-win`,
`gw-workstation-wsl-2`, `gw-workstation-win-vaultspec`). The machine-led form loses
the project when runners are listed per-repository, which is the only way they are
ever listed.

Most significantly, this repository's Linux runner is named `gw-workstation-wsl-2` but
is a Docker container, not a WSL runner. The name asserts a hosting mechanism it does
not use. That is what made this runner hard to locate: searching WSL for it finds
nothing.

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
