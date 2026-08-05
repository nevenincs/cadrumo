---
tags:
  - '#audit'
  - '#ci-runner-standardization'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:6ace3c904e6925f8321ebaeac192da3214ba65d21b8adc8bf0f77d4557d5e47e'
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

### duplicate-task-needs-elevation | medium | The redundant WSL launcher cannot be disabled without an elevated session

Actioning the duplicate-launcher hazard was attempted under explicit operator authority
and is **blocked on privilege, not on judgement**. The scheduled task lives in the root
task folder; modifying it requires an elevated session, and the agent session runs
unelevated. Both `Disable-ScheduledTask` and `schtasks /change /disable` return access
denied. The task's state was re-read after each attempt and is unchanged, so the failed
attempts altered nothing.

No privilege escalation was attempted. Acquiring rights the session was not granted, on
an operator's own machine, is not within the authority to action a finding.

The pre-state was captured and confirms the duplication precisely: the task is enabled
with a logon trigger and runs the same runner directory that a systemd unit inside WSL
already owns, where a listener has been serving for over a day, with the registration
online and idle. The remedy remains a one-line elevated `Disable-ScheduledTask`,
reversible with `Enable-ScheduledTask`, and it interrupts nothing that is serving
because systemd holds the live listener.

### superseded-duplicate-already-inert | low | The second duplicate task is confirmed superseded and already in its correct end state

The disabled cadrumo runner task was checked rather than assumed. It carries an action
and trigger type identical to the live, named task for the same runner, is already
disabled, and its task-info records that it has never run at all — a never-run result
code and a null last-run timestamp, not a failure.

So it is genuinely superseded, genuinely inert, and its correct end state is the one it
is already in. Deleting it would need the same elevation the item above lacks, and
would buy nothing: a disabled never-run task consumes no resource and cannot fire.
Recording it as known-superseded is the complete remedy, and is cheaper than deletion.

### linux-runner-death-root-caused | high | The container did not die of the cleanup prune; it died of an unrecoverable registration crash-loop

The orphaned state volume was inspected read-only and carries the whole story in its
diagnostics. The earlier reading — that the cleanup hook's container prune reaped a
stopped container and thereby cost the capacity — is wrong about causation. The prune
was the last step, not the cause.

The evidenced sequence: the runner served normally for three days, its logs large and
busy. Its final session then ends **mid-poll with no shutdown record at all** — token
refreshes continuing at ordinary intervals, then nothing. That absence is the signature
of a container stopped externally rather than one that failed: a runner that crashes
says so, and a runner asked to stop logs its shutdown. Neither appears.

Eleven days of silence follow. The service then does what it documents: it deletes
registrations that have not connected recently. When the container next started — the
restart policy firing after a daemon or host restart — it woke into a world where its
identity no longer existed, and logged exactly that: the registration has been deleted
from the server, please re-configure. It exited code 1, the restart policy started it
again, and it repeated the cycle seven times in thirty seconds before ending stopped.

Two consequences follow, and both matter more than the original finding.

**A deleted registration plus an always-restart policy is an unrecoverable loop.** The
container cannot re-register: that needs a fresh registration token it has no way to
obtain. So it burns restarts forever without any possibility of self-healing, and the
only signal is a log nobody reads inside a container nobody is watching. This is why
the volume must not be reused — any container built on those credentials reproduces the
same loop indefinitely.

**The real defect is that nothing noticed.** A runner stopped serving, its registration
was deleted for inactivity eleven days later, it crash-looped, and it was reaped — and
the first thing to observe any of it was an unrelated inventory audit two weeks on. The
fleet has no liveness signal. Restoring the container without adding one would rebuild
the capacity and leave intact the condition that let it vanish unremarked, which is the
same reset-instead-of-fix this campaign has refused twice already.

The likely trigger deserves recording without being overstated: the stop falls in the
same window as the provisioning of three other repositories' runners on this box, whose
directories were created across the two following days. A container stopped during that
work and never restarted fits every observation, but the logs do not name who stopped
it, and no evidence here raises that from consistent to established.

### linux-pair-restored | high | The second Linux runner is restored, named to convention, and verified at capability parity

A fresh registration was created under operator authority: a new state volume, the
tracked entrypoint, and the runner configured from a registration token that was never
written to output. The orphaned volume was not reused and was not touched; it remains
in place for the operator to dispose of. The container came up, created a session, and
is listening for jobs; the service reports it online.

It was named to the convention at birth — product-led, no host name. That is the one
naming change in this campaign with **zero** cost: a new registration can be named
correctly for free, where renaming an existing one is a deregister/re-register cycle.
The fleet now contains its first conforming runner name, which is a better argument for
the convention than any amount of prose.

**Capability parity turned out to be the load-bearing part, and verifying rather than
assuming caught a hazard this restore itself introduced.** Both Linux runners carry
identical labels, so a job takes whichever is free. A newly built runner is missing
everything the base image does not ship, and the repository's own documentation lists
exactly what that is. The new runner initially lacked Homebrew, which the acquisition
lane requires and which fails at that lane's first step — a coin-flip failure
reproducing only half the time, the worst debugging shape available. It was installed
at the canonical path per the documented procedure, and both runners now verify
equivalent on every documented axis.

One earlier reading is corrected here: an initial check appeared to show the existing
runner carrying its tooling only in the container's writable layer. That was an
artefact of the probe — a login shell resets the path and resolved a redundant copy
first. The volume-resident install is present on both. The general caution stands and is
now written into the runners README, but the existing runner was not defective.

### fleet-has-no-liveness-signal | high | Nothing detects a runner that stops; this is the condition that must change

The restore rebuilds capacity but does not address why the loss went unnoticed for two
weeks, and that gap is the more durable defect. A runner stopped, was deregistered for
inactivity, crash-looped, and was reaped, and the first thing to observe any step was an
unrelated inventory audit. Nothing polls, nothing alerts, and the only evidence lived in
a log inside a container nobody opens.

A design is proposed rather than landed, because a monitor is a standing surface and
adding one unasked is how the next unwatched signal gets created.

**What it queries.** The per-repository runners endpoint, comparing the set of names
reporting online against an expected set. Cheap, authoritative, and independent of the
host — it observes what the service believes, which is the thing that actually decides
whether jobs get scheduled.

**Where the expectation is declared.** In the repository, beside the runner
documentation, as data rather than prose — the same file the fleet table is generated
from, so a runner added or retired updates the expectation in the same change. An
expectation living only in the monitor drifts from the fleet the moment someone
provisions without touching it.

**How it fails loudly, and to whom.** As a scheduled workflow job that fails when the
observed set does not match the expected one. A failing job on the repository's own
Actions tab is a signal the team already watches for other reasons, which is the whole
point — it inherits an existing habit rather than asking for a new one. It must name
which runner is missing, not merely that the count is wrong.

**How it avoids becoming another unwatched signal.** Three properties. It must fail the
job rather than log a warning, because warnings in green runs are read by nobody. It
must run somewhere that does not depend on the fleet it is checking — a hosted runner,
not a self-hosted one, or a total outage silences the very alarm meant to report it.
And it must be quiet when healthy: a check that fires routinely trains its audience to
ignore it, which is the failure mode one level up from the one it was built to fix.

**Cost.** One scheduled API call per interval against a rate limit measured in
thousands per hour, on a hosted runner, consuming nothing from the box that already
carries eight runners. A daily interval would have caught this loss inside the window
before deregistration, when a restart would still have been sufficient.

### liveness-design-collides-with-no-schedule-ruling | high | The proposed monitor's trigger breaks a standing operator ruling; the design is re-cast as a choice

The liveness design above is sound except in its trigger, and the trigger is
disqualifying. The CI workflow header records an operator ruling dated three weeks
before this audit: the slow conformance surfaces are manual-dispatch only, **no
scheduled runs**. Verified independently rather than taken on trust — no workflow in
this repository declares a `schedule:` trigger, and the only triggers in use tree-wide
are push and manual dispatch. The ruling is honoured completely.

A scheduled monitor would therefore be the first scheduled run in the repository and
would breach that ruling. It is not proposed. What follows is a choice for the operator,
not a request.

**Option A — scheduled check, needs an exception to the ruling.** The design as
written. Its concrete argument is not hypothetical: the runner that vanished stopped on
one day, was deregistered roughly eleven days later, and only then became
unrecoverable. **A daily check would have fired inside that window, while a restart was
still sufficient and the state volume was still alive.** The cost of the exception is
one scheduled job; the cost of not having it was a fortnight of halved Linux capacity
that nobody detected.

**Option B — same check, no exception needed.** The identical comparison run as a job
inside an existing dispatch-triggered workflow, or as a pre-flight step on the release
path. It violates nothing and could land immediately. Its weakness is honest and
should not be glossed: it only observes when somebody runs something, so a fleet that
degrades during a quiet period stays undetected until the next release — which is
precisely the scenario that produced this incident. It converts an unbounded blind
window into one bounded by release cadence. That is a real improvement and a partial
one.

The three anti-decay properties bind under either option. The check must **fail**, not
warn, because warnings inside green runs are read by nobody. It must run on a **hosted**
runner, never a self-hosted one, or a total fleet outage silences the alarm built to
report it. And it must be **quiet when healthy**, because a check that fires routinely
trains its audience to ignore it — which is this same defect one level up, rebuilt by
the fix.

### restore-repairs-the-per-push-split | high | The missing runner was silently defeating the operator's own ten-minute-wall design

Reading the no-schedule ruling in context surfaced something the capacity finding
understated. The CI workflow header records a second operator directive, from the day
before: build and test infrastructure must not take fifty minutes per step. The response
was to split per-push verification into two parallel jobs — static checks and the unit
suite — **explicitly sized against the two Linux runners**.

With only one runner online, those two deliberately-parallel jobs had no second executor
and ran one after the other. The per-push split, which exists specifically to hold a
ten-minute wall, had been quietly serialised into roughly double its intended
wall-clock for two weeks.

That sharpens the capacity finding from a general concern into a specific defeat: the
fleet was not merely under-provisioned against its documentation, it was failing an
explicit operator performance directive, invisibly, because the failure mode was
slowness rather than error. Restoring the pair repairs the parallelism the split was
designed around — and it means the restore's value can be measured on the next push
rather than argued.

### windows-runner-exit-is-documented-behaviour | critical | Not a fault: it was cancelled by hand mid-job, and by design it does not come back

Read-only diagnosis, no relaunch attempted. The evidence is unambiguous and it does not
support calling this a defect.

The final log records a clean, deliberate shutdown: repeated *runner will be shutdown
for UserCancelled*, an *Exiting* line, the in-flight job moved to Canceled, the runner
session deleted, and *runner execution been cancelled*. There is no crash, no exception,
no resource failure. The scheduled task's non-zero exit is the console-cancellation exit
code, not an error condition.

The timing tells the rest. A job finished **Failed** at 10:37:05, the next job started
one second later, and thirty seconds into it the cancellation arrived. That reads as a
person watching a failure, interrupting the runner at the console, and not restarting
it — which also means an unrelated job was killed as collateral.

The hosting mode is confirmed exactly as the runners README describes: the runner is
**not** configured as a service. No service marker exists on disk and no corresponding
service is registered. The documentation states that this runner runs interactively in a
console session and that killing the listener does not auto-resume it. Both hold. The
only thing that relaunches it is an interactive logon firing its scheduled task.

**So the honest answer is the one worth giving: this is the design working as
documented, and the design cannot stay up unattended.** A console-session runner dies
with its console, dies on an accidental interrupt, takes its running job down with it,
and then waits for a human to log in. Restarting it is a host act that buys time until
the next interruption; it is not a fix, and treating it as one would guarantee a repeat.

### windows-runner-is-on-a-deregistration-clock | critical | The Linux incident is the preview; this one has roughly a fortnight before it is unrecoverable

The two outages in this audit are the same story at different stages, and reading them
together changes the urgency of the second.

The Linux runner stopped, sat untouched, and after roughly eleven days the service
deleted its registration for inactivity. From that moment its state volume was
permanently dead: any container built on it wakes with credentials naming a registration
that no longer exists and crash-loops forever, because re-registering needs a token it
cannot obtain. Recovery required a wholly new registration.

The Windows runner is now roughly one day into that same silence. Its configuration is
still valid and a relaunch would still restore it. That will not remain true. If it is
left down for the same interval, its registration is deleted too, and the remedy escalates
from "start the runner" to "re-register from scratch" — on the one platform where
provisioning is manual, un-containerised, and cannot be scripted from a peer machine.

That converts the Windows outage from a queueing problem into a **deadline**. The
queued packaging jobs are the visible cost; the invisible one is that the cheap remedy
expires. This is not a prediction — it is a description of what already happened once on
this box, to a runner whose recovery cost a full re-provisioning.

The durable fix is the hosting mode, not the restart. Installing the runner as a service
is the documented alternative and the README already names the migration path, including
that the diagnostic hook then takes effect on a service restart rather than a console
relaunch. That is an operator act on operator-owned infrastructure, and it is the only
change that stops this recurring at every logoff, stray interrupt, and reboot.

### directory-renames-are-not-cheap | medium | The rename judged cheapest is the one that cannot be done safely

The naming proposal assumed directory renames were the low-cost half — no re-registration,
no downtime. Measurement contradicts that for every directory that actually diverges.

Each runner directory is named by **absolute path** in two places that a rename would
silently invalidate: the action of the logon scheduled task that launches it, and the
job-completed hook path in the runner's own environment file. Editing the task requires
an elevated session, which this one does not have and did not acquire.

So the rename and the task edit must land together, and only one half is reachable.
Doing the reachable half alone would leave a launcher pointing at a path that no longer
exists — converting the Windows runner from *down but relaunchable at the next logon*
into *down with its relauncher broken*, which directly worsens the deregistration
deadline recorded above. The dashboard directory carries the identical coupling on
another project's surface.

The two conforming directories need no change. The two divergent ones are blocked on the
same elevation as the duplicate-task item. **The cheap half of the naming work turns out
to be the blocked half, and the expensive half — runner names — turns out to be the one
that could proceed.** That is the reverse of the proposal's assumption and is recorded
so the next reader does not re-derive the cheap-looking answer.

### runner-names-now-conform | medium | Both Linux runners renamed with no outage, because the restored pair provided cover

The runner carrying a name that asserted the wrong hosting mechanism has been
re-registered under the convention, and its sibling with it. Both now identify
product-first and carry no host name.

The restore made this safe. Renaming a registration is a deregister/re-register cycle,
which on a single runner is an outage; with a healthy pair sharing one label set, the
surviving runner covers the label while its sibling is reconfigured. Both were idle,
each was stopped and reconfigured in turn, and each returned online listening for jobs.
The stale registration left behind by the rename was removed rather than left as another
orphan.

The sequencing is the lesson: the restore was justified on capacity, but it also created
the conditions that made the naming fix free. Work ordered by risk produced an
opportunity that work ordered by tidiness would have missed — attempting these renames
before the pair existed would have meant real downtime on the only Linux runner.

### macbook-host-entirely-offline | critical | The second build host is down, and six registrations across four repositories are now on the deregistration clock

Observed during this session rather than sought: **every runner hosted on the macOS
build machine is offline, across all four repositories** — both of this repository's, and
one or two each belonging to the other three. Two of them were online when this audit
began. The host does not answer on the network.

This is a whole-machine outage, not a per-repository fault, and nothing in this campaign
touched that machine — the work here was confined to containers and registrations on the
Windows/WSL box.

Its significance is the clock, and the clock is now the central finding of this audit
rather than an aside. The mechanism established from the lost Linux runner applies
unchanged: a runner that merely stops is deregistered for inactivity after roughly a
fortnight, and at that moment its stored configuration becomes permanently dead. That
happened once here and cost a full re-provisioning. **Six registrations are now sitting
in that same window simultaneously**, on a host that is manually provisioned and cannot
be rebuilt from this machine.

So the fleet-wide state is worse than any single finding suggested. This repository has
two working runners — both Linux X64, both restored or renamed during this audit — and
is carrying an offline Windows runner and two offline ARM runners. Its macOS, Linux
ARM64 and Windows lanes are all unschedulable at once.

And it is the third independent instance of the same root defect: **nothing watches the
fleet.** One runner was lost to it entirely, one is a day into it, and six more entered
the window during the few hours this audit took to write. A liveness check is no longer
a tidiness proposal; it is the only control that would have surfaced any of these before
the cheap remedy expired.

### macbook-outage-timed | critical | The clock started at 12:00 today, which makes the cheap remedy still available for all six

Refining the outage finding above with the timestamp, because the age of an outage
determines which remedy is still on the table. The mesh-network peer record reports the
host last seen at **12:00:00 on the day of this audit** — minutes before it was noticed,
not at some unknown earlier point.

That is materially better news than the finding first implied. The full inactivity window
is still ahead of all six registrations. Every one of them is still recoverable by
starting its listener, and none has yet reached the point where its stored configuration
dies and re-registration becomes the only route — the point the lost Linux runner passed
unobserved.

So the correct characterisation is not that six registrations are somewhere in the
window, but that **six registrations entered the window at 12:00 today**, and the cheap
remedy is available to all of them for roughly a fortnight. What is needed is an operator
action on the host, not a re-provisioning exercise. No attempt was made to start them:
that is a host act on the operator's own machine, and this session has no non-interactive
privileged path to it.

### status-representation-is-not-liveness | high | A peer status line can read healthy for a host that has just gone, and a monitor built on it would report this fleet green

This finding exists because the outage was briefly retracted on the strength of a status
line, and the retraction was itself wrong. It is recorded because the trap will catch the
next reader the same way.

The mesh-network status output describes a peer's **last-known route and cumulative
traffic**. Shortly after a host disappears it still shows a plausible direct route and
large byte counters, because those are historical facts about a connection that used to
work — they are not assertions that the peer is reachable now. Read quickly, that
presents as a healthy host. The word describing the connection type sits on the same line
as the word describing liveness, and only the second one is the state.

The probes that actually discriminate are a mesh ping, which times out with no reply, and
the structured status output, whose explicit online field reads false and whose last-seen
field carries the timestamp. Both were run for this audit and both agree with the
GitHub-side view.

A name-resolution failure is a separate trap in the same family and was originally
mistaken for one: the host's ordinary name does not resolve, which is indistinguishable
from a host being down until a probe on the mesh name discriminates. Here both readings
happened to point the same way, but they could have diverged.

**This is direct evidence for what the proposed liveness check must query.** The design
above already specifies observing what the *service* believes rather than the host, and
this is exactly why: throughout this outage the GitHub runners endpoint reported all six
registrations offline — correctly, immediately, and unambiguously — while a host-level
status line still read as active. A monitor built on host status would have reported this
fleet healthy at the moment it was most degraded. The service's view is the one that
decides whether jobs get scheduled, so it is also the only view worth alarming on.

### macbook-outage-mechanism-is-a-sleep-timer | critical | One unsupervised userland process is a single point of failure for an entire machine's fleet

The outage above had no stated mechanism. Durable operator notes supply one, and it is
specific, recurrent, and fixable.

The macOS build host carries a **one-minute system sleep timer**, held off solely by a
persistent keep-awake process. Nothing supervises that process. If it dies, the machine
sleeps within a minute, and everything running on it stops with it.

That explains every symptom without remainder: six registrations across four
repositories dropping *simultaneously* rather than drifting, the host declining SSH
connections, the mesh ping going unanswered, and the peer record still advertising a
stale route. A machine that slept behaves exactly like this; a machine with six
independently failing runners does not.

**Attribution is deliberately limited.** The keep-awake process could not be observed to
have died, because the host is unreachable precisely when the question matters — the
evidence is unavailable for the same reason the finding exists. The honest statement is
that the documented sleep behaviour explains every observation, not that the cause was
witnessed. The operator notes independently record this same failure recurring, which is
corroboration rather than proof.

Three things follow, and each is stronger than the untimed outage finding it refines.

**It is a single point of failure at machine scale.** One unsupervised userland process
dying silently drops six registrations belonging to four different repositories onto the
inactivity clock. Nothing about that is proportionate: the blast radius of the failure is
an entire build host's fleet, and the thing holding it up is a process with no restart
policy and no alarm.

**It recurs by construction.** A one-minute sleep timer held off by an unsupervised
process is not a freak event that happened once; it is a mechanism that will fire again
whenever that process ends, and the operator notes confirm it already has. This is the
second concrete justification for the liveness check proposed above, and the stronger of
the two: the failure mode is *guaranteed to recur* and emits no signal anywhere in the
system.

**The remedy is cheap at both horizons.** Waking the host recovers all six registrations,
because the inactivity window is still open. Disabling sleep at the power-management
level stops the recurrence permanently. Neither requires re-provisioning, and that
distinction is what the outage timestamp already established. Both are host acts needing
privileged access this session does not have, so both are operator work — but the durable
one should not wait for the next occurrence to justify itself.

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
