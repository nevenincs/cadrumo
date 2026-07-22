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

### homebrew-linux-arm64-sigill-SOLVED | medium | root cause is pac-ret retaa under Apple Virtualization; a verified fix exists

RESOLVED after the long elimination trail below. A debugger on the faulting
process named the instruction: `retaa`, the ARMv8.3 pointer-authentication
combined authenticate-and-return, in the cffi backend's `get_unique_type`. That
is why pointer authentication looked eliminated earlier — the HINT-space
`paciasp`/`autiasp` are no-ops on cores without the feature and appear in working
builds too, but `retaa` is a real instruction that faults. Apple's
Virtualization.framework guest (the colima virtual machine on the Apple-silicon
host) does not execute it and raises an illegal-instruction fault; the same class
is documented independently at dotnet/runtime issue 122608 (SIGILL on Apple
Virtualization from pointer authentication). The instruction enters the build
because Homebrew's compiler shim injects `-mbranch-protection=standard` whenever
its `HOMEBREW_CCCFG` carries the `b` flag (`shims/super/cc`, `branch_protection?`
is exactly `config.include?("b")`); the distribution's own gcc does not default to
it. It surfaces at library load rather than lazily because the build environment
resolves relocations eagerly.

The fix is verified on the real formula, three of three clean installs plus a
load under eager binding: drop the `b` from `HOMEBREW_CCCFG` in the formula so no
compiled extension carries `retaa`, and install the argon2 bindings with build
isolation disabled so they build against that pac-free virtual-environment cffi
rather than a fresh isolated-overlay cffi that would re-inherit the shim's
pac-ret. The bindings' build backend must be present for the isolation-off build
— setuptools plus setuptools-scm, the latter pinned to the self-contained 8.x
line since 10.x splits its versioning into a separate distribution. This is a
generator change, not an infrastructure or scope decision.

Landed in the Homebrew formula generator with its build backend added and the
generator's own tests updated for the new install method and resource count; the
generator suite is green. Verification so far is the mechanism on the exact
minimal reproducer (three clean installs plus a load under eager binding) and the
unit tests. The end-to-end confirmation — a real Homebrew acquisition run whose
arm64 leg mints the row — still has to run, and it needs the fix commit on origin
plus a smoke run at that commit; both are release-pipeline deployment steps, not
further debugging. One tradeoff to record: dropping pac-ret removes a hardening
that only functions on hardware with pointer authentication anyway, and keeping
it makes the package uninstallable on the Apple-Virtualization build host, so
compatibility is the correct call here.

### homebrew-linux-arm64-cryptography-overlay-sigill | high | the real formula fails one step past argon2: cryptography's build-isolation overlay cffi faults the same way

The real cadrumo formula (all 70 resources, generated from the published
v0.2.1 release assets) was run through genuine `brew install` on the arm64
container to de-risk the pac-ret fix beyond the minimal argon2 reproducer. It
failed at `cryptography` 48.0.1 — a resource the previous runs never reached,
because argon2 always crashed first. Faulthandler instrumentation (formula-level
`ENV["PYTHONFAULTHANDLER"] = "1"` plus `--keep-tmp`) captured the exact death:
`cryptography-cffi`'s `build.rs` runs `_cffi_src/build_openssl.py` under the
venv python, which dies `Fatal Python error: Illegal instruction` importing
`_cffi_backend` from the pip build-isolation overlay
(`pip-build-env-*/overlay/.../cffi/api.py` line 41). Same class as argon2: a
build-time load of an overlay-built cffi that carries pac-ret, which the
formula-scope `HOMEBREW_CCCFG` `b`-drop does not cure (the drop was confirmed
active — `OS.linux? && Hardware::CPU.arm?` evaluates true under brew ruby on
the guest, and all direct venv resource builds through the alphabet up to
`cryptography` succeeded, including the venv `cffi` itself).

The empirical contract, consistent across argon2 and cryptography: the
`b`-drop covers DIRECT venv resource builds; any resource whose PEP 517
build-isolation overlay must compile-and-load cffi still faults and needs
`build_isolation: false` so it builds against the pac-free venv cffi. In the
70-resource set exactly two resources import cffi at build time:
`argon2-cffi-bindings` (fixed) and `cryptography` (fails). The cryptography
fix additionally needs `maturin` present in the venv for the isolation-off
build (a pinned PyPI sdist resource, like `setuptools-scm` for argon2;
maturin's own overlay build is safe — it never imports cffi). Resources
alphabetically after `cryptography` (greenlet, lxml, pillow, pikepdf,
pydantic-core, rpds-py, rtoml, pyyaml, sqlalchemy, …) remain UNVERIFIED on
arm64 until a full green install; none of them imports cffi at build time, so
no further instance of this class is expected, but the 3-of-3 green gate must
still run.

Verification-technique notes for the next pass: modern brew refuses
path installs (`brew tap-new` a throwaway local tap and copy the formula in);
the repository is private so the release-asset URLs 404 for unauthenticated
curl inside the container — pre-seed `~/.cache/Homebrew/downloads/` with
`sha256(url)--basename`-named copies of the three cadrumo sdists; clear
`~/.cache/pip` between runs; `ENV["PYTHONFAULTHANDLER"] = "1"` in the tap copy
turns the empty-output subprocess death into a full faulting stack.

RESOLVED (2026-07-22). The full 72-resource formula builds and pours green on
the Apple-virtualization arm64 container; `LD_BIND_NOW=1` imports of
`_cffi_backend`, `_argon2_cffi_bindings`, and `cryptography` (with
`default_backend()`), `aeat --version` -> `CADRUMO 0.2.1`, and an argon2id hash
all succeed. Reaching green required two prerequisites the minimal argon2
reproducer had masked, because in the full formula cryptography-in-batch always
faulted before argon2's isolation-off step ever ran: (1) a `python -m venv`
(what `virtualenv_create` builds) ships pip but NOT setuptools, and Homebrew
installs every resource `--no-deps`, so nothing pulls setuptools in
transitively; both isolation-off builds then die `BackendUnavailable: Cannot
import 'setuptools.build_meta'`. Fixed by pinning `setuptools` as an explicit
venv resource next to `setuptools-scm`/`maturin`. (2) cryptography's `maturin`
backend shells out to the `maturin` executable by bare name; the sdist install
places that binary at `libexec/bin`, bundles no copy in the Python package, and
adds no PATH entry, so both the isolation-off build and the `--no-binary=:all:`
buildpath rebuild die `FileNotFoundError: 'maturin'`. Fixed by
`ENV.prepend_path "PATH", libexec/"bin"` before the cryptography install (it
persists into the buildpath rebuild, which needs it too). The resource tail
(greenlet, lxml, pillow, pikepdf, pydantic-core, rpds-py, rtoml, pyyaml,
sqlalchemy, ...) built with no further cffi-overlay faults, confirming argon2
and cryptography were the only two cffi-at-build resources. The 3-of-3
determinism gate passed: three consecutive `brew install --build-from-source`
runs poured byte-identically (23,257 files, 670.2MB each), each with a green
`LD_BIND_NOW=1` import of `_cffi_backend`/`_argon2_cffi_bindings`/`cryptography`
and `aeat --version` -> `CADRUMO 0.2.1`.

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

Both candidate fixes were carried through a real formula install and both fail,
which localises the trigger conclusively. The pre-built-wheel path is out:
Homebrew forces a source-only install on every resource, so a wheel resource is
rejected as not installable. The no-build-isolation path was implemented and
verified applied — the build log carries the disable-isolation flag on the
bindings' build — and it still faulted with the same illegal instruction. The
same flag, run by hand outside Homebrew against a virtual environment holding an
already-built working cffi, builds the bindings cleanly. Same flag, opposite
outcomes, the only difference being whether Homebrew drives the build.

That is the conclusion, not a step toward one: the fault is bound to Homebrew's
own build-execution context on this virtual machine, and nothing reconstructed
outside that context reproduces it, so no in-formula flag reliably removes it.
The bindings' build backend was also pinned along the way — its setuptools-scm
must be the self-contained 8.x line, since 10.x splits its versioning into a
separate distribution the isolated build cannot resolve — but that only changes
which step the run reaches, not the fault.

The compiler identity was the last reconstructible variable and it is eliminated
too: Homebrew's named compiler resolves to the system gcc 13.3.0 (the two are the
same binary), and cffi built with it plus Homebrew's optimisation flags
constructs an FFI object cleanly. Every individual component of the build —
compiler, flags, build isolation, environment variables, the sandbox, the
compiler shim, pointer authentication, SSE2 detection — has now been tested in
isolation and works; only the full Homebrew build orchestration faults, and it
does so on every run while no reduction of it reproduces the fault. The
reconstructible surface is exhausted.

Because the trigger is the build environment itself, the durable resolutions are
operational, not a formula edit: run the Linux-arm64 Homebrew leg on real arm64
Linux hardware instead of the colima virtual machine on the Apple-silicon host,
or state that architecture's from-source Homebrew support level explicitly and
drop its row from the required contract. A complete instruction-level root cause
would still need a debugger attached to the live Homebrew build subprocess, but
the support decision does not wait on that reading. Three independent reconstructions were tried and all confirm the same
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
