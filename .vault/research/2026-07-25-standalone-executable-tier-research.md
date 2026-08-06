---
tags:
  - '#research'
  - '#standalone-executable-tier'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:22f5f81a5653d211d28b3dbb04c00b62b64ff91a1589275e96cc3a714fa6a9dd'
related:
  - "[[2026-07-25-account-distribution-standard-adr]]"
  - "[[2026-07-20-release-asset-transport-adr]]"
  - "[[2026-07-22-homebrew-arm64-pac-ret-adr]]"
---

# `standalone-executable-tier` research: `how cadrumo builds standalone per-platform executables`

The account channel rule selects a `standalone-executable` tier for cadrumo and the
product declares it unbuilt in `docs/_data/download_channels.toml` under the matrix
`pending_tiers` key. The question is which mechanism produces those binaries. The evidence
changes the framing twice: the native-extension surface that makes freezers look risky is
a Homebrew artefact rather than a property of the dependency set, and the sealed release
cohort structurally cannot carry per-platform binaries as members. What remains decisive
is not build feasibility - several mechanisms are feasible - but whether the mechanism
creates a fourth build of the product whose behaviour must be proven independently of the
three that already ship.

Semantic search was not usable for this pass. The code index answers confidently while
serving a fraction of the tree, so every claim below rests on a direct read or an `rg`
sweep against the working tree, and absence claims are bounded to the files named.

## Findings

### The heavy native surface is a Homebrew source-build constraint, not a property of the dependency set

The `cmake` / `pkgconf` / `rust` build dependencies and the `jpeg-turbo` / `libyaml` /
`openssl@3` / `qpdf` runtime dependencies exist because Homebrew forbids binary wheels and
builds all of its venv resources from sdists (`packaging/homebrew/generate.py:422-432`).
Every native runtime dependency in the locked set ships a prebuilt `cp313` or `abi3` wheel
for linux x86-64, linux aarch64, macOS arm64 and win_amd64 - verified by reading the wheel
URL lists in `uv.lock` for `cryptography@48.0.1` (`cp39-abi3`, manylinux 2.28 and 2.34 for
both aarch64 and x86-64, plus `win_amd64`), `pikepdf@10.10.0`, `pypdfium2@5.12.1`,
`pydantic-core@2.46.4`, `rtoml@0.13.0`, `lxml@6.1.1`, `pyyaml@6.0.3` and
`sqlalchemy@2.0.51`. A mechanism that consumes wheels therefore compiles nothing and needs
no C or Rust toolchain for the payload.

### The Linux-arm64 SIGILL does not reach a wheel-consuming mechanism

`argon2-cffi-bindings@25.1.0` publishes a
`cp39-abi3-manylinux_2_26_aarch64.manylinux_2_28_aarch64` wheel in the locked set. The
exit `-4` SIGILL recorded against the `homebrew-linux-arm64` row in plan row `P01.S03` of
`2026-07-17-post-release-distribution-plan` is a source build of that package under
Homebrew's toolchain, and `2026-07-22-homebrew-arm64-pac-ret-adr` already records the root
cause as Homebrew's injected branch-protection flag faulting under Apple Virtualization,
noting in the same record that PyPI wheels carry no such injection. The fault is therefore
not a reason to exclude Linux arm64 from a wheel-consuming standalone mechanism; runner
and evidence capacity is.

### The sealed cohort cannot carry per-platform binaries as members

`dev/packaging/release_cohort.py` builds every artefact in one process on one machine and
stamps `platform.system()` and `platform.machine()` into a single `BuildIdentity`
(`dev/packaging/release_cohort.py:275-276`), pinning `uv 0.11.29` and CPython `3.13.11`
and refusing otherwise (`:44-47`, `:258-267`). The `CohortManifest` completeness validator
in `dev/packaging/cohort_manifest.py` requires the artifact name set to equal
`REQUIRED_ARTIFACT_KINDS` exactly - twelve members today, all platform-independent. Three
binaries built on three hosts cannot satisfy a one-host manifest without changing what
`BuildIdentity` means. The kind taxonomy is separately constrained: a channel row's
`artifact_kinds` is typed as a tuple of `ArtifactKind`, and the partition validator
requires every `ArtifactKind` to be surfaced by exactly one channel row
(`dev/docs/download_matrix.py:164`, `:231-251`), so a new channel row cannot exist without
a new `ArtifactKind` member - while nothing today asserts the converse, that every
`ArtifactKind` is a cohort member.

### The transport for per-host artefacts already exists and is proven

`2026-07-20-release-asset-transport-adr` established draft releases per producing run with
a per-run evidence manifest recording workflow path, run id, run attempt, head SHA and a
per-asset sha256 and size table, verified in three layers before use. That is the shape a
set of per-host binaries needs, and `dev/packaging/acquire_github_release.py` already
re-acquires published release assets and verifies each against manifest digests.

### The product already bundles its full payload, and it is large

The three cohort wheels measured in `var/release-cohort/python/` are 49.7 MB for
`cadrumo-0.2.1-py3-none-any.whl`, 76.7 MB for the manuals companion and 64.3 MB for the
official-data companion - about 191 MB of wheels over a 615 MB `src/cadrumo/_data` source
tree. `packaging/mcpb/build.py` already embeds those exact three wheel byte sequences and
bootstraps a venv from them, producing the 179.5 MB `cadrumo-0.2.1.mcpb`. An
embed-everything container is therefore proven in-repo; what the mcpb does not remove is
the interpreter prerequisite - its manifest launches uv (`packaging/mcpb/build.py:46`,
`:57`), so it presupposes uv on the host. That prerequisite is what this tier exists to
remove.

### Freezers create a fourth build; installers do not

PyInstaller and Nuitka both emit an artefact whose module graph, extension loading and
data-file layout differ from the wheel every other channel serves. Two properties of this
codebase make that expensive rather than routine: the dynamic-import rule records
`importlib.import_module` with runtime-built module strings as a sanctioned, in-use
technique, and the swarm-audit rule records that hundreds of function-local imports are
deferred to break cycles - both are the classic hidden-import failure mode for static
module-graph analysis. Published comparisons put PyInstaller at roughly 30 s where Nuitka
takes 5-15 min for a medium application because every module passes a C compiler, with
Nuitka winning startup latency
(https://ahmedsyntax.com/2026-comparison-pyinstaller-vs-cx-freeze-vs-nui/,
https://x321.org/empirical-pyinstaller-vs-nuitka-vs-cx_freeze/). Neither difference bears
on the fourth-build cost, which is the same for both.

Zipapp mechanisms are excluded by construction rather than by trade-off: both `shiv` and
stdlib `zipapp` produce an archive that requires a Python interpreter already on the
target, which is the prerequisite the tier removes, and neither can import a native
extension from the archive without extracting it.

### PyApp is the account's existing answer for this tier

`2026-07-25-account-distribution-standard-research` records `vaultspec-core` shipping a
`binaries.yml` matrix build of standalone executables for four targets via PyApp,
attaching eight assets plus a checksums file per release. PyApp is a Rust launcher that
provisions a managed CPython and installs the project at first run rather than freezing
it: distribution embedding puts the interpreter inside the binary so no runtime fetch is
needed for it, a project-path option embeds one wheel or sdist, a project dependency-file
option embeds a requirements file, an extra-args option forwards installer flags such as
binary-only resolution, and a uv option makes uv the installer
(https://ofek.dev/pyapp/latest/config/distribution/,
https://ofek.dev/pyapp/latest/config/project/,
https://ofek.dev/pyapp/latest/config/installation/). Two limits matter: it embeds one
project artefact, not three, so the two data companions cannot ride the project-path
option; and every build method requires a Rust toolchain, since PyApp publishes no
pre-built binaries (https://ofek.dev/pyapp/latest/build/). Its most recent tag is `v0.29.0`
(2025-10-15) with master active through 2026-06-26, including a 2026-06-11 refresh of the
default CPython distributions (https://github.com/ofek/pyapp/commits/master/).

uv has no first-party bundling verb; astral-sh/uv issue 5802 requesting one is open. The
third-party `uvbox` (AmadeusITGroup) and `py-app-standalone` (jlevy) occupy the same niche
as PyApp's payload, the latter producing a relocatable install directory rather than a
single native entry point.

### Digest-pinning a first-run install is reachable with existing machinery

`dev/packaging/uv_constraints.py` already exports runtime constraints for the mcpb build
and currently passes a no-hashes flag (`dev/packaging/uv_constraints.py:54`). Dropping
that flag yields a hash-bearing requirements file, which combined with an embedded
dependency file and a require-hashes install would bind a first-run install to the exact
sealed cohort wheel digests - the same bytes the registry channel publishes.

### What an evidence row must execute is already fixed by the existing rows

Channel rows are declared per channel in `docs/_data/download_channels.toml` and the
required set is derived from claimed channels by `required_evidence_rows`
(`dev/docs/download_matrix.py:301`), consumed by `dev/release/readiness.py:181`. A row's
execution isolation demands that checkout imports and ambient product executables are
removed and that at least one installed-executable identity carries a name, path and
sha256 (`dev/packaging/evidence.py:90-98`), and the Homebrew precedent recorded in plan
row `P02.S08` drives the installed CLI and MCP oracles to compute a known modelo-200 cuota
integra from the installed location. The existing three python rows are minted on the
self-hosted Linux X64, Windows X64 and macOS ARM64 labels
(`.github/workflows/packaging-smoke.yml`); no workflow declares a Linux arm64 label
outside the Homebrew matrix.

### Not investigated

No binary was built, so there is no measured size, startup time or first-run duration for
cadrumo under any mechanism. PyApp's behaviour with a hash-pinned dependency file under
its uv installer is read from documentation, not executed. Whether the two data companions
install cleanly under binary-only resolution inside a PyApp-managed venv is untested. The
`vaultspec-core` `binaries.yml` was not read directly; it is taken from the account
research record. Whether a Rust toolchain is present on the Windows and macOS self-hosted
runners was not checked. Code signing and notarization - Windows SmartScreen and macOS
Gatekeeper on an unsigned downloaded binary - were not investigated at all, and are a
user-facing acquisition cost this pass does not size.

## Sources

- `packaging/homebrew/generate.py:422-432`
- `uv.lock`, wheel URL lists for the locked native dependencies
- `dev/packaging/release_cohort.py:44-47`, `:258-267`, `:275-276`
- `dev/packaging/cohort_manifest.py`
- `dev/docs/download_matrix.py:164`, `:231-251`, `:301`
- `dev/packaging/evidence.py:90-98`
- `dev/packaging/acquire_github_release.py`
- `dev/packaging/uv_constraints.py:54`
- `dev/release/readiness.py:181`
- `packaging/mcpb/build.py:46`, `:57`
- `docs/_data/download_channels.toml`
- `.github/workflows/packaging-smoke.yml`, `.github/workflows/packaging-homebrew.yml`
- `var/release-cohort/python/` and `var/release-cohort/mcpb/`, measured artefact sizes
- https://ofek.dev/pyapp/latest/build/
- https://ofek.dev/pyapp/latest/config/distribution/
- https://ofek.dev/pyapp/latest/config/project/
- https://ofek.dev/pyapp/latest/config/installation/
- https://github.com/ofek/pyapp/commits/master/
- https://github.com/astral-sh/uv/issues/5802
- https://github.com/AmadeusITGroup/uvbox
- https://github.com/jlevy/py-app-standalone
- https://ahmedsyntax.com/2026-comparison-pyinstaller-vs-cx-freeze-vs-nui/
- https://x321.org/empirical-pyinstaller-vs-nuitka-vs-cx_freeze/

The PyInstaller and Nuitka timing figures are secondary-source summaries, not measured
here. The PyApp release date was read from the master commit log after the releases page
rendered an inconsistent year; the tag date was not confirmed through the GitHub API.
