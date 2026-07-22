---
tags:
  - '#audit'
  - '#post-release-distribution'
date: '2026-07-21'
modified: '2026-07-21'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

# `post-release-distribution` audit: `v0.2.1 publication record and outstanding fast-follow`

## Scope

Records what shipped as v0.2.1 and audits what the release still owes. No
document previously recorded the publication event itself. Every claim below was
verified against live state on 2026-07-21 — the GitHub release, the PyPI index,
the repository variables, environments and secrets, the runner fleet, and the
local evidence directory — rather than carried forward from campaign notes.

## Findings

### publication-bypassed-pipeline | medium | v0.2.1 was promoted by direct operator order, not through the publish workflow

The release is published at tag `v0.2.1`, dated 2026-07-21T12:46:11Z, carrying
eight assets: wheel and sdist for each of the three distributions, the `.mcpb`
bundle, and the sealed evidence manifest. It was an operator-ordered direct
promotion of a verified cohort from a green packaging run. The publication
authority `publish-release.yml` was not exercised, so its gates remain unproven
in anger and the release notes carry the bypass on the record.

### pypi-absent | high | the distributions are not on PyPI

The PyPI JSON index returns 404 for the project, so the published wheels and
sdists exist only as GitHub release assets. Every install path that a reader is
told to use — plain pip, and uvx — is therefore unsatisfiable, while the docs
claims gate treats those channels as claimed. Publishing is the single largest
piece of outstanding release debt.

### evidence-rows-absent | high | no distribution-evidence rows exist locally

The local readiness directory holds zero records, so the aggregation gate cannot
reach a complete matrix and `publish-release.yml` cannot pass its validation
gate. Rows are minted only by real per-platform lane runs; none of the required
runs have produced one into this tree.

### publish-flag-unset | high | the publication opt-in variable is absent

The repository defines the scoop-bucket, homebrew-tap and marketplace repository
variables and their tokens, and the `pypi`, `pypi-data-manuals`,
`pypi-data-official` and `release` environments all exist. The one missing
prerequisite is the publish opt-in variable, which Gate 1 requires; without it
the publication authority refuses before doing anything. The downstream
repositories it would push to both exist and are reachable.

### runner-fleet-offline | critical | the lanes that mint the missing rows cannot run

Three of the five self-hosted runners are offline: the Windows build host and
both runners hosted on the ARM MacBook. Only the two Linux container runners are
online, and both are busy. The Scoop lane needs Windows; the Homebrew lane needs
macOS ARM64 and Linux ARM64; the smoke matrix needs Windows and macOS for two of
its three python rows. With hosted runners barred by standing operator mandate,
no substitute capacity exists, so the remaining evidence cannot be produced at
all until those machines are powered on. This gates every other finding above.

### macos-intel-row-retired | low | the evidence contract narrowed from twelve rows to eleven

macOS Intel was dropped from all provisioning on operator directive the same day,
retiring the `homebrew-macos-x86-64` row along with the Rosetta runner
registration and the formula's macOS architecture split. Any readiness arithmetic
or runbook prose still counting twelve rows is stale.

### fleet-restored-and-matrix-green | high | the runner blocker is resolved and five rows now exist

Superseding the runner-fleet-offline and evidence-rows-absent findings above. The
Windows build host was not an operator-only item: it runs its listener
interactively rather than as a service, so nothing restarts it after a drop, and
starting that listener returned it to service. With the MacBook also powered on,
the fleet reached five of five. The first fully successful three-OS packaging
smoke run followed, all eight jobs including the manifest seal, and both
acquisition lanes were dispatched from it. Five of the eleven evidence rows now
exist: the three python rows on the smoke draft, plus the homebrew Linux x86-64
and macOS arm64 rows.

### macos-runner-resolved-as-x86-64 | high | Rosetta residue made an ARM runner build as Intel

The macOS legs failed resolving `torch` for an x86-64 macOS platform while
running on the ARM64-labelled runner. Two layers caused it. The reused checkout
carried a virtual environment built on an x86-64 interpreter, and beneath that
the uv managed-Python store held two Intel builds alongside one native arm64
build; uv selects the highest patch version, which was Intel. Removing both Intel
interpreters and the stale environment turned the macOS legs green. This is
residue from the retired Rosetta runner, not a packaging defect, and it is the
reason a machine can look correctly labelled while building for the wrong
architecture.

### homebrew-linux-arm64-sigill | medium | the arm64 leg dies on an illegal instruction, cause narrowed by elimination

The Linux arm64 Homebrew leg fails building `argon2-cffi-bindings`, whose
metadata subprocess exits on signal 4, an illegal instruction. Eliminated as
causes: architecture, since the colima VM, its docker daemon, the container and
its kernel are all native aarch64; resource contention, since it fails
identically when run alone; the package itself, which builds cleanly in that same
container; a source-built cffi, which builds and imports cleanly; a
copies-based virtual environment, since both copy and symlink environments run
correctly, including compiled-extension imports; and exotic compiler flags, since
brew uses plain gcc there with no optimisation flags set. The failure appears only
inside the from-source formula build, whose subprocess runs under the formula's
own environment interpreter. The remaining hypothesis needs the tap regenerated
and the formula build reproduced by hand.

### scoop-lane-container-mode-conflict | medium | the Scoop lane and the Linux runners cannot share one docker daemon

The Scoop lane's preflight requires docker in Windows-container mode, but the
build host runs Linux mode because the two Linux runners are themselves
containers on that same daemon. A daemon serves one mode at a time, so the two
requirements are mutually exclusive on one host and switching would stop both
Linux runners mid-job. This is a topology decision, not a defect.

## Recommendations

Treat a dropped runner as a first-class check before concluding that CI capacity
is an operator matter: the Windows listener is interactive and silently stays
down until someone starts it, which masqueraded as an operator blocker here.
Sweep a retired architecture's toolchain residue, not just its provisioning: the
uv managed-Python store outlived the runner that installed it and silently
redirected an ARM machine to Intel builds.

Resume the arm64 investigation from the narrowed hypothesis space recorded above
rather than re-deriving it: regenerate the tap and reproduce the formula's
from-source build by hand, comparing the formula environment's interpreter
against a hand-built one, since every simpler explanation is already eliminated.
Decide the Scoop topology explicitly — either give that lane its own docker host,
or accept stopping the Linux runners for the duration of a mode switch — because
no amount of lane work resolves a one-mode-at-a-time daemon.

Capture the four real-client rows in Claude Desktop and Cowork; they gate the
matrix regardless of the other two lanes, so publication cannot pass until they
exist. Set the publication opt-in variable only once the matrix is complete —
arming it earlier only arms a gate that must refuse — and then dispatch the
publication authority so the PyPI upload runs through the gated pipeline rather
than a second bypass, which also retires the publication-bypassed-pipeline
finding. Treat the eleven-row contract as current when reconciling any remaining
runbook arithmetic.
