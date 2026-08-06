---
tags:
  - '#adr'
  - '#scoop-runner-topology'
date: '2026-07-22'
modified: '2026-07-28'
body_hash: 'sha256:1ecf65d91b175b9bbb77acc391a50dc397ea7efec9ee44400d9b2e6d00afe393'
related:
  - "[[2026-07-21-post-release-distribution-v0-2-1-publication-audit]]"
---

# `scoop-runner-topology` adr: `Scoop windows-x86-64 evidence lane runs on a native Windows runner, not the shared Docker daemon` | (**status:** `accepted`)

## Problem Statement

The `scoop-windows-x86-64` distribution-evidence row needs a Windows
environment to execute a real Scoop acquisition. The only Docker daemon in the
runner fleet (Docker Desktop on the operator's Windows workstation) runs in
Linux-container mode and hosts the two standing Linux runners; Docker Desktop
supports exactly one container mode at a time, so a Windows-container Scoop
lane on that daemon would require stopping the Linux runners for every mode
switch. An infrastructure-topology ruling is needed so the row is mintable
without starving the Linux lanes.

## Considerations

- Docker Desktop's Linux/Windows container modes are mutually exclusive per
  daemon; a mode switch tears down every running Linux container.
- The two Linux runners carry standing CI load; stopping them for Scoop runs
  couples an occasional evidence lane to the fleet's availability.
- Scoop is explicitly a user-scoped, no-admin package manager: a real
  acquisition needs only a normal Windows user profile, PowerShell, and
  network — not a container.
- Evidence honesty requires a real install on a real Windows-x86-64 surface;
  a container adds isolation but no additional evidentiary value for a
  user-scope tool.
- A second physical/virtual Windows Docker host is real hardware/provisioning
  cost for one occasional lane.

## Considered options

- **Windows-container lane on the shared daemon (mode switch):** zero new
  hardware; every run stops both Linux runners and requires two mode
  switches. Rejected — couples an occasional lane to fleet downtime and is
  operationally error-prone.
- **Dedicated Windows-container Docker host:** clean isolation; new
  hardware/VM to provision and patch for a lane that does not need
  containerization. Rejected as primary; retained as fallback if host
  isolation requirements tighten.
- **Native Windows runner on the existing workstation (chosen):** a GitHub
  Actions runner service under a dedicated low-privilege local user, labelled
  for the scoop lane; Scoop installs into that user's profile and the lane
  never touches the Docker daemon. No mode switches, no new hardware.

## Constraints

- The workstation is operator-owned; provisioning the runner service and the
  dedicated user is an operator action an agent cannot perform.
- The scoop lane must clean the dedicated user's Scoop profile
  (`~/scoop`) between runs to keep acquisitions independent; the lane script
  owns that reset, not the runner image.
- The lane shares the workstation's CPU/disk with interactive use; evidence
  runs are occasional (per release), so contention is acceptable.

## Implementation

Provision a native GitHub Actions self-hosted runner on the Windows
workstation under a dedicated non-admin local user, labelled (e.g.
`windows-scoop`) so only the scoop acquisition lane schedules onto it. The
lane installs/uninstalls cadrumo via Scoop in that user's profile, emits the
`scoop-windows-x86-64` evidence row through the existing emitter, and resets
the Scoop profile between runs. The Docker daemon stays permanently in
Linux-container mode; the Linux runners are untouched.

## Rationale

Scoop's user-scope install model makes containerization unnecessary for
evidentiary purposes, so the only benefit of the Docker options — isolation —
is not load-bearing here, while their costs (fleet downtime or new hardware)
are real. A native runner under a dedicated user gives adequate isolation for
a no-admin package manager, keeps the Linux lanes running, and needs no new
hardware. Operator action implied: create the local user, install and label
the runner service; this is the sole remaining gate on the row.

## Consequences

- The `scoop-windows-x86-64` row becomes mintable without touching the shared
  Docker daemon; Linux runner availability is decoupled from the Scoop lane.
- The workstation hosts one more standing service; its dedicated user's Scoop
  profile is lane-owned state.
- If a future policy demands container-grade isolation for Windows lanes, the
  dedicated Windows-container host fallback supersedes this topology via a
  new ADR.
- Until the operator provisions the runner, the row stays honestly unminted —
  no SDK-driven or faked evidence is admissible.

### Reconciliation with the account distribution standard

Two accepted records name Scoop, and a reader meeting both should not have to
derive their relationship. `2026-07-25-account-distribution-standard-adr` is
**unaffected by this record, and this record is unaffected by it**, because the
two decide disjoint axes.

This record decides the **execution host** of the Scoop evidence lane: the
`scoop-windows-x86-64` row is minted on a native Windows self-hosted runner
under a dedicated non-admin user, and the shared Docker daemon stays in
Linux-container mode so the standing Linux runners are untouched. It says
nothing about where a Scoop manifest is published.

The account distribution standard decides the **artefact destination**: one
shared account repository, `nevenincs/homebrew-tap`, serves `Formula/` for
Homebrew and `bucket/` for Scoop, so a user runs one bucket-add ever regardless
of product count. It says nothing about which machine executes an acquisition.

Neither decision constrains the other. Changing the publication target does not
change which host can run a Scoop install, and changing the runner topology does
not move a manifest. The orthogonality is the same one the standard states
internally — a repository name and a bucket directory are disjoint constraints —
extended one axis further to the runner that consumes them.

Where the two axes meet is at the **public reacquisition** lane, not at this
record's acquisition row. That distinction was stated the wrong way round when
this subsection was first written and is corrected here against the shipped
harnesses.

The clean acquisition gate stages its own bucket: the lane rewrites the
cohort-bound manifest to local artefact paths, commits it into a throwaway git
repository, and adds that as a Scoop bucket over a `file:` URI, so the whole
install-update-uninstall-reinstall cycle runs against verified local bytes. Its
emitted acquisition source is that local bucket URI, and the evidence model
places no public-URL constraint on the field. The `scoop-windows-x86-64` row
therefore has exactly **one** remaining precondition, the execution host this
record provisions — a published manifest is not among them.

The public reacquisition script is the lane that installs from a published
bucket source rather than staging a local one, and it refuses instructively when
that bucket does not yet serve the package. That row, and the install-claim
documentation gated on it, is where this record's host and the standard's
destination are both required at once. Even there it is a conjunction of two
independent preconditions, not a conflict between two rulings, and neither
record supersedes any part of the other.
