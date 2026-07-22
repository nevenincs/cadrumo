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

Conflict, unresolved. The same no-binary directive does not work through a real
formula install: brew's environment does not carry it into the overlay, so the
overlay still takes its default cffi. And a source-built cffi that loads correctly
in a standalone environment still crashed once when the overlay used a
locally-tagged wheel under brew, the opposite of the standalone result. Comparing
the two overlay backend binaries directly deepened this rather than resolving it:
in both the failing and the passing harness the backend is a source-built,
unstripped object, they are different binaries, and neither contains any exotic
instruction-set opcode in its own executable section. So the illegal instruction
is very likely not in the cffi backend at all but in a library it loads — libffi
is the immediate suspect, since the cffi backend links it and a libffi compiled
with native tuning would place the trapping instruction exactly where the fault
handler points, at module load rather than in Python-visible code. That library
has not been examined. Whoever resumes should disassemble the libffi the overlay
links, not the cffi backend, and treat "which cffi wheel" as a proxy that has now
outlived its usefulness.

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

Resume the arm64 investigation at libffi, not cffi. The backend binaries were
already compared: both source-built, both free of exotic opcodes in their own
text, so the trapping instruction is almost certainly in a linked library loaded
alongside the backend, and libffi is the direct dependency that fits. Identify
the libffi the overlay resolves, disassemble it, and find the illegal
instruction; that pins whether this is native-tuned code the virtual machine
cannot run. Do not re-test the sandbox, the compiler shim, environment filtering,
architecture, contention, the package standalone, environment layout, install
ordering, optimisation flags on cffi itself, or the cffi wheel-versus-source
distinction; all are eliminated or shown to be proxies above, and one hypothesis
was already withdrawn for resting on a partial reconstruction.

Once the offending library is known, the fix is to make that one dependency
compile for a portable baseline inside the isolated overlay through a channel brew
does not strip — a pip configuration file staged into the build, or the formula
generator emitting the dependency as its own resource so build isolation never
fetches a pre-tuned build — not the environment variable tried here, which brew
removes before the overlay sees it.

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
