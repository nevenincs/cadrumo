---
tags:
  - '#adr'
  - '#standalone-executable-tier'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-25-standalone-executable-tier-research]]"
  - "[[2026-07-25-account-distribution-standard-adr]]"
  - "[[2026-07-20-release-asset-transport-adr]]"
---

# `standalone-executable-tier` adr: `cadrumo ships standalone executables as PyApp launchers over the sealed cohort, not frozen builds` | (**status:** `proposed`)

## Problem Statement

The account channel rule selects a `standalone-executable` tier for cadrumo, and the
product declares it unbuilt. The practical consequence is that a taxpayer or adviser
cannot install cadrumo at all today: the registry channel presupposes a Python toolchain
and the managed installers are unpublished. This record decides the mechanism that
produces the binaries, the platforms shipped first, how the artefacts bind to a release,
what proves the channel, and whether the tier displaces the managed installers.

The decision is forced now rather than later because two other things wait behind it. The
community-windows tier submits a binary, so it cannot start until a binary exists. And the
mechanism determines whether the product acquires a fourth independent build of itself, a
commitment far cheaper to decline before the first binary ships than after users hold one.

## Considerations

- The heavy native build surface is a Homebrew source-build artefact, not a property of
  the dependency set; every native runtime dependency ships a prebuilt wheel for all four
  target platforms, per `2026-07-25-standalone-executable-tier-research`.
- The Linux-arm64 SIGILL is a Homebrew source build of one package under an injected
  branch-protection flag, already root-caused in `2026-07-22-homebrew-arm64-pac-ret-adr`;
  it does not reach a mechanism that installs wheels.
- The sealed cohort is built by one process on one machine and its manifest demands an
  exact, platform-independent member set, so per-platform binaries cannot be members
  without redefining what a cohort build is.
- A channel row cannot exist without a new `ArtifactKind`, because the channel descriptor
  types that field as the cohort taxonomy and requires every kind to be surfaced by
  exactly one row.
- Transport for per-host artefacts is solved: `2026-07-20-release-asset-transport-adr`
  already carries per-run assets under a digest manifest with layered verification.
- The payload is about 191 MB of wheels; the mcpb already embeds those exact bytes, so an
  embed-everything container is proven in-repo but still presupposes uv on the host.
- The codebase defers hundreds of function-local imports and uses runtime-built
  `importlib` module strings, both sanctioned by standing rules and both the classic
  failure mode for a freezer's static module graph.
- Evidence is proportional to claims: a tier declared pending blocks nothing, and a tier
  claimed must produce a row per platform that executes installed bytes in isolation.

## Considered options

- **PyApp launcher over the sealed cohort (chosen).** A small native binary embedding a
  managed CPython that provisions the product at first run from digest-pinned wheels.
  Pros: executes the same bytes the registry channel publishes; compiles nothing from the
  payload; already the account's shipped answer for this tier. Cons: needs a Rust
  toolchain per builder; first run needs network unless the payload is embedded; embeds
  one project artefact, so the two data companions need a resolution route.
- **PyInstaller.** Widest adoption, fastest build, one-file or one-folder output.
  Rejected: it produces a fourth build of the product whose import graph and data-file
  collection must be proven against a dynamic-import-heavy codebase and a 615 MB data
  tree, and one-file mode re-extracts the whole payload on every launch.
- **Nuitka.** Best startup and runtime, near drop-in. Rejected for the same fourth-build
  reason in its strongest form - the shipped object code would differ from every other
  channel - plus a C toolchain per platform and 5-15 minute compiles.
- **shiv or stdlib zipapp.** Rejected outright: the artefact still requires a Python
  interpreter on the target, which is exactly the prerequisite this tier exists to remove,
  and native extensions cannot be imported from the archive without extraction.
- **A hand-rolled uv bundle (uvbox, py-app-standalone, or an in-house relocatable venv).**
  Technically closest to the chosen option, and the mcpb bootstrap already proves the
  pattern in-repo. Rejected as primary: no native single entry point, no account
  precedent, and PyApp already composes uv as its installer, so the uv benefit is
  available without owning the bootstrapper.
- **Ship nothing yet and keep the tier pending.** Rejected: it is the status quo in which
  no non-developer can install the product, and it holds the community-windows tier
  hostage indefinitely.

## Constraints

- PyApp is a third-party dependency whose latest tag is `v0.29.0` (2025-10-15) with an
  active master through mid-2026. The build must pin an exact source archive by digest
  rather than track a moving reference, so a dormant upstream degrades to a frozen,
  reproducible input rather than a broken build.
- Every PyApp build method requires a Rust toolchain on the building host; PyApp publishes
  no pre-built binaries. Toolchain presence on the Windows and macOS self-hosted runners
  is unconfirmed and is a prerequisite of the first build.
- PyApp embeds one project artefact. Cadrumo needs three wheels, so the companions must
  resolve through an embedded, hash-pinned dependency file rather than through embedding.
  The requirements exporter already exists and currently suppresses hashes; enabling them
  is the whole change.
- No binary has been built, so size, startup time and first-run duration are unmeasured
  for this product. The first implementation step is a measurement, and a first-run cost
  materially worse than installing the same wheels with pip reopens the payload-embedding
  question.
- Code signing and notarization are unexamined. An unsigned downloaded binary meets
  Windows SmartScreen and macOS Gatekeeper, which is a real acquisition cost this record
  does not size and does not resolve.
- The tier depends on the sealed-cohort and evidence apparatus staying in force; it adds a
  consumer of both and changes neither.

## Implementation

The binary is a launcher, not a build. For each target platform a PyApp source archive is
compiled with the interpreter distribution embedded, the product entry point set to the
`aeat` console script, and an embedded requirements file pinning the three product
distributions to the sealed cohort's exact wheel digests, installed with hashes required
and binary-only resolution. At first run the launcher provisions its embedded interpreter,
installs those exact wheels, and every later run executes the provisioned environment
directly. Because the pinned digests are the cohort's own, the standalone channel cannot
serve bytes that differ from the registry channel; a drift is an install-time refusal
rather than a silent divergence.

The artefacts are cohort-derived rather than cohort members. The cohort keeps its
one-host, exact-member-set contract untouched. A separate per-platform build job, on the
runner whose platform it targets, consumes the sealed cohort, produces one binary, and
records the originating cohort identifier alongside the binary digest. The set is sealed
by a standalone-set manifest of the same shape and verification discipline as the existing
per-run evidence manifest, and travels as release assets on the same transport. One new
`ArtifactKind` member is added so the channel row can declare it; because that kind is not
a cohort member, the taxonomy's split becomes explicit data - a named set of
cohort-derived kinds, with a gate asserting that every kind is either a required cohort
member or a declared derived kind, so the hole cannot open silently.

First ship covers linux x86-64, macOS arm64 and windows x86-64: exactly the three
self-hosted runners that already mint the python evidence rows, and therefore exactly the
three platforms whose channel can be proven rather than asserted. Linux arm64 and macOS
x86-64 are deferred for runner and evidence capacity, not for the SIGILL, which does not
apply to a wheel-consuming mechanism; both remain buildable additions once a lane exists.

A new `standalone` channel row declares the tier with one evidence row per shipped
platform. A passing row downloads the published asset, verifies its digest against the
standalone-set manifest, and drives the binary in an isolated environment with checkout
imports and ambient product executables removed, recording the installed executable's own
path and digest and completing the same grounded tax oracle every other channel row
completes. The row therefore proves the first-run provisioning path, not merely that a
file downloads. Until those rows pass the tier stays declared-pending and blocks nothing,
exactly as the evidence-proportional-to-claims rule intends.

## Rationale

The knockout criterion is that the standalone channel must not create a fourth build of
the product. PyInstaller and Nuitka each produce an artefact whose module graph, native
extension loading and data-file layout differ from the wheels every other channel serves,
so the product's correctness would have to be re-established for that artefact and
re-established again on every dependency bump. Against a codebase that deliberately defers
hundreds of imports and builds module targets as runtime strings, and a 615 MB data tree a
freezer must be told about file by file, that is a standing liability with no offsetting
gain: the tier's requirement is that a user without a toolchain can run the command, not
that the command starts faster. PyApp discharges the requirement by installing the
published bytes, so the standalone channel is provably the registry channel with the
prerequisite removed.

Two lesser edges confirm it rather than carry it. The account distribution standard exists
to stop each product inventing its own arrangement, and PyApp is already the account's
shipped mechanism for this exact tier. And the mechanism turns the reproducibility posture
into an asset instead of a hazard: hash-pinning the first-run install to the cohort
digests makes the binary refuse anything but the sealed release, which no freezer can
offer because a frozen artefact has no install step to pin.

## Consequences

Good: a non-developer acquires cadrumo with one download on all three shipped platforms;
the community-windows tier is unblocked because a binary now exists to submit; the
standalone channel is byte-bound to the registry channel, so the two cannot drift; the
cohort's one-host contract survives untouched; and the artefact carries no compiled
product code, so no new native build surface enters the release.

Bad: first run needs network and downloads about 191 MB, so the binary is a bootstrapper
rather than a self-contained program, and a user on a metered or offline machine is served
worse than by an embed-everything artefact. The build acquires a Rust toolchain
prerequisite on three runners and a third-party dependency with a slow release cadence.
Three more evidence rows must pass before the tier may be claimed, on runners that already
carry the release lanes. Unsigned binaries will meet operating-system warnings this record
does not address.

Neutral: the tier complements the managed installers rather than replacing them. Homebrew
and Scoop retain the upgrade, uninstall and PATH management a bare binary does not
provide, the account rule selects both tiers independently, and dropping one for cadrumo
alone would fork the standard. The one interaction worth revisiting separately is whether
the Scoop manifest should eventually point at the binary rather than at a Python install;
that is a simplification this record neither makes nor forecloses.
