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
correctly, including compiled-extension imports; exotic compiler flags, since
brew uses plain gcc there with no optimisation flags set; and the cross-interpreter
install shape the formula uses, which succeeds when run outside brew.

The compiler-shim hypothesis recorded in an earlier revision of this document is
WITHDRAWN. It came from applying brew's summary environment dump by hand, which
made the shim refuse with a message about the build tool having reset the
environment. A real formula install disproves it: a minimal formula that builds
cffi from source under genuine brew completes cleanly. The summary dump is not
the full build environment, and reproducing with it produces a false positive —
the caveat recorded alongside that hypothesis is what caught it.

What replaces it is a minimal reproducer and an exact crash site. A four-resource
formula — argon2-cffi as the target, with pycparser, cffi and
argon2-cffi-bindings as resources, built through the standard
virtualenv-with-resources helper — fails identically under a real from-source
install in seconds, needing no release artefacts. cffi alone succeeds in the same
harness, so the trigger is specific to the argon2 bindings, not to compiling C
extensions generally.

Enabling the interpreter's fault handler from the formula turns the silent death
into a stack. The crash is the dynamic loader creating the cffi backend
extension module, reached from the argon2 bindings' FFI build script calling the
cffi API constructor at metadata time. The extension being loaded lives in pip's
build-isolation overlay, not in the formula environment. So the failing artefact
is the cffi backend as built or fetched for the isolated build, and it executes
an instruction the virtual machine refuses.

Everything that would explain that away has been tested and eliminated: forcing
the overlay to build cffi from source rather than take a wheel (it then builds a
locally-tagged wheel and still crashes); overriding the optimisation flags from
the formula; compiling cffi by hand with the same native-tuned flags Homebrew
exports and constructing an FFI object, which succeeds; and the compiler
identity, since the compiler the environment names is not present at the path it
names.

The failure is fully deterministic: five of five real formula installs fail. It
is not the brew sandbox (disabling it does not help) and not the brew compiler
shim or environment filtering (bypassing those does not help). What is
established, and what conflicts, both matter for the next pass.

Established. The crash is the dynamic loader creating the cffi backend extension,
and the copy being loaded lives in pip's build-isolation overlay rather than the
formula environment. When build isolation is disabled so the target compiles
against the environment's own cffi, the metadata step that crashes instead
completes cleanly. In a standalone virtual environment, forcing pip to rebuild
cffi from source inside the isolated overlay — by exporting the no-binary
directive into the environment the isolated build inherits — also makes the whole
install succeed. Both point the finger at the specific cffi backend that the
overlay obtains by default, which is the pre-built PyPI aarch64 wheel.

Conflict, unresolved — and every quick test overturned the prior hypothesis,
which is itself the finding. The no-binary directive does not survive brew's
environment into the overlay. A source-built cffi that loads cleanly standalone
still crashed once under brew. Comparing the two overlay backend binaries showed
both source-built, unstripped, different, and neither carrying an exotic opcode in
its own text — which pointed at a linked library, most naturally libffi. But
inspecting the crashing backend's linkage disproved that too: it links the stock
system libffi at the standard multiarch path, not a Homebrew or native-tuned
build, so the portable-library theory does not hold either. At this point the two
things that are solid — the crash is at load of the overlay's cffi backend, and
forcing that dependency to build for a portable baseline in a clean environment
avoids it — coexist with a chain of specific mechanisms each of which was
eliminated by the next test. That pattern says the trapping instruction is
reached through something the quick harnesses do not faithfully reproduce, and
that root-causing it needs a debugger stopping on the signal to read the faulting
program counter and the exact mapped object at that address, not more
build-permutation experiments. It was not carried to that point.

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

Two documented candidates were researched and tested against the real formula,
and both are recorded here so they are not retried blind. The first is
argon2-cffi-bindings' own SSE2 auto-detection, controlled by
ARGON2_CFFI_USE_SSE2: it is a red herring for this crash, because that flag
governs argon2's own optimized C which compiles after metadata, whereas the fault
is in the cffi backend load during metadata, and setting it to 0 through the real
formula did not help (three of three still failed). The second is ARM pointer
authentication and branch-target-identification, the classic virtual-machine
illegal-instruction culprits: also eliminated, because the crashing backend and a
known-working backend both contain the same PAC and BTI instructions and the
working one runs, so this virtual machine executes them correctly. Homebrew
already compiles with the portable -march=armv8-a, not -march=native, and forcing
a generic CPU target through the formula did not help either.

One fix direction is proven in principle and is the strongest lead. Building the
argon2 bindings against an already-installed working cffi instead of letting pip
create a fresh isolated overlay — a real installer run with build isolation
disabled — clears the crashing metadata step. Wiring that into a generated
Homebrew formula is unfinished formula engineering, not a mystery: the formula
must stage the build backend (setuptools, wheel, setuptools-scm) and cffi into
the virtual environment first, then install the bindings with isolation disabled,
and be verified green several times over. Supplying the bindings as a pre-built
aarch64 wheel would also avoid the build entirely, at the cost of Homebrew's
from-source expectation.

Research and experiment converge on the failure class and the fix. A CPython fix
for an illegal instruction on older Arm (its issue 125444) is the same pattern —
compiled code executing a processor instruction the running core does not
support — though it is specific to 32-bit Arm and its exact instruction does not
exist on this 64-bit target, so it confirms the category without being the same
bug. The recurring recommendation across the cffi and argon2 ecosystem for
architecture-specific source-build crashes is consistent with what the
experiments here already showed: do not compile the offending dependency from
source in the crashing context; take a pre-built wheel or build it against a
known-good copy. That is the same conclusion reached two independent ways, so the
fix direction is settled even though a shipped, green formula was not produced.

The fix is now pinned to specific code, and the alternative is ruled out. The
pre-built-wheel path does not work: Homebrew forces a source-only install on
every resource, so a wheel resource is rejected as not installable. That leaves
the no-build-isolation path, and it is proven at the decisive point — under a
real formula install, the virtual environment's own cffi builds from source and
loads without faulting, and only the fresh isolated overlay's cffi crashes. A
formula that installs the bindings against that working environment cffi with
isolation disabled therefore avoids the crash; the version tried here failed only
because it reached the network for the build backend, not because of any fault.

The remaining work is bounded generator engineering. The generator emits a single
`virtualenv_install_with_resources` call, which builds every resource with
isolation on, so the bindings' build fetches its backend into the crashing
overlay. The bindings declare their build backend as setuptools and
setuptools-scm, and Homebrew's Python provides neither, so the fix must add those
two (and their own resolution) as formula resources, install them and cffi into
the virtual environment first, then install the bindings with build isolation
disabled against that environment. That is a resource-graph change to the
generator plus its lockfile resolution, followed by regenerating the tap and
running the acquisition lane to green several times over — well-defined, but more
than a one-line edit because of the build-backend resource cascade.

If that formula still does not land cleanly, resume with a debugger attached to
the LIVE build, not a replay, to read the exact faulting instruction — but the
fix does not depend on that reading; only a complete root-cause explanation
would. Three independent reconstructions were tried and all confirm the same
thing: importing the crashing overlay's cffi backend directly does not fault,
constructing an FFI object with an equivalent cffi does not fault, and both run
clean under the debugger — while the real formula build faults deterministically,
five times of five. The crash therefore does not survive extraction from pip's
live build subprocess; it exists only inside that running process. Every
reconstruction-based approach is now proven futile, so the debugger must be
attached to the subprocess pip actually spawns. The mechanism is to interpose on
the interpreter pip launches for the metadata hook — a wrapper on the build-backend
Python that re-execs it under a debugger set to stop on the illegal-instruction
signal — then read the faulting program counter and map it to the loaded object.
This is the one path not yet taken and the only one the evidence still permits. Everything cheap has been tried: the sandbox, the compiler shim, environment
filtering, architecture, contention, the package standalone, source-built cffi,
environment layout, install ordering, cffi optimisation flags, the cffi
wheel-versus-source split, and the linked libffi (which is the stock system
build) are all eliminated or shown to be proxies. Two hypotheses were published
and withdrawn this session for resting on partial reconstructions, so trust only a
faulting-address reading or a real formula install from here.

Two things are nonetheless solid enough to act on. The crash is at load of the
cffi backend from pip's build-isolation overlay, and forcing that one dependency
to build for a portable baseline in a clean environment avoids it. Whatever the
faulting instruction turns out to be, the fix shape is the same: make the overlay
build its cffi (and whatever it links) for a portable target through a channel
brew does not strip — a pip configuration file staged into the build, or the
formula generator emitting the dependency as its own resource — since the plain
environment variable is removed before the overlay sees it.

Weigh this against the debugging cost. The lane exists to prove one architecture's
from-source Homebrew install. If the faulting address lands in code the virtual
machine simply cannot execute, the honest resolutions are to run the leg on
hardware that executes it or to state that architecture's support level
explicitly, rather than to hold a release behind a permanently red lane.

A durable alternative worth weighing against further debugging: this lane exists
to prove a from-source Homebrew install on one architecture. If the cause is the
virtual machine's instruction coverage rather than anything the project controls,
the honest resolutions are to run that leg on hardware that executes the
instructions, or to state the architecture's support level explicitly, rather
than to keep a permanently red lane in a release gate.
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
