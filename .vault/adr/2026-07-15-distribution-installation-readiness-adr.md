---
tags:
  - '#adr'
  - '#distribution-installation-readiness'
date: '2026-07-15'
modified: '2026-07-15'
related:
  - '[[2026-07-15-distribution-installation-readiness-research]]'
  - '[[2026-07-15-distribution-installation-readiness-reference]]'
  - '[[2026-06-28-product-packaging-adr]]'
  - '[[2026-07-03-claude-ecosystem-packaging-adr]]'
  - '[[2026-07-04-release-readiness-gate-adr]]'
---

# `distribution-installation-readiness` adr: `Immutable tested-cohort promotion and executable acquisition proof` | (**status:** `accepted`)

## Problem Statement

An installable artifact performing its advertised work is a binding product invariant,
not an architectural option and not a release-time preference. This decision does not
seek approval for whether Cadrumo artifacts should work. It selects the composition,
identity, execution, and promotion mechanisms that make that already-mandated outcome
measurable and enforceable for every claimed acquisition path.

Cadrumo has substantial build and isolated-install machinery, but no single evidence
chain proves that the bytes offered through an advertised acquisition path are the bytes
tested, installable, callable, and functional. Existing lanes rebuild independently,
readiness inspects incomplete evidence, publication rebuilds again, public acquisition
paths are absent or stale, and documentation describes paths that outside users cannot
complete.

Construction and schema validation are not executable proof. A wheel must run its
installed commands; an MCP server must complete a real protocol interaction; a Claude
plugin and MCPB must install in their claimed clients and start their pinned server; a
Scoop distribution must install in a clean Windows environment; a Homebrew formula must
install through a real tap on every claimed macOS/Linux row. Every channel must expose
working commands and complete a grounded tax calculation. Platform neutrality is a
claim requiring execution on named platforms, not an inference from source structure.

Publication authority is also contradictory: accepted decisions require local-only,
token-based human publication while the repository implements GitHub Actions OIDC
Trusted Publishing. A single authority and evidence contract are required.

## Considerations

- Functional installed behavior is the definition of completion. A channel that has not
  installed and performed real tax work has not been delivered, regardless of whether
  its archive, manifest, or metadata was generated successfully.
- Approval follows artifact behavior: building, validating, or passing source-tree tests
  is insufficient.
- Every distribution surface for one version must derive from one source commit and
  remain byte-identical through testing and promotion.
- The cohort includes the root wheel and sdist, companion wheels, generated Claude
  plugin tree, marketplace snapshot, MCPB, release metadata, Scoop material, and a
  Homebrew tap/formula snapshot.
- Evidence distinguishes construction, direct artifact installation, installed
  execution, client execution, channel acquisition, publication, and post-publication
  verification.
- Public documentation creates a product claim and must not lead availability.
- Scoop is Windows-specific; Homebrew evidence is platform-specific and does not by
  itself establish support for unexecuted macOS/Linux rows.
- PyPI and release uploads may be immutable; publishing replacement bytes that were not
  tested is unacceptable.
- Client-dependent claims require declared real client versions. An unavailable client
  cannot become a successful `skipped` result.
- Python, plugin, MCPB, and platform requirements need one consistent authority.
- A user-facing install cannot be “slim” if it cannot load the registry and calculate.
  File-size-driven splitting is an internal artifact concern, not a degraded public
  product mode.

## Considered options

1. **Remain source-only.** Correct all documentation to authorized-source installation
   and remove public distribution claims. Honest and low risk, but abandons the intended
   PyPI, Claude, MCPB, Scoop, and Homebrew acquisition architecture.
2. **Promote one immutable, fully evidenced cohort.** Build once, exercise the same
   hashes through applicable installation, client, platform, and staged acquisition
   gates, publish those bytes through one manual authority, verify public acquisition,
   and only then promote documentation. Chosen: it directly satisfies executable-artifact
   approval at the cost of release time and infrastructure.
3. **Publish first and test afterward.** Rejected because it exposes immutable broken
   packages and stale guidance before acceptance can protect users.
4. **Allow local and CI publication authorities.** Rejected because divergent
   credentials, rebuild paths, and evidence cannot prove which authority published which
   bytes.

## Constraints

- One clean source archive at an exact commit and version produces the cohort once.
  Every later lane accepts cohort paths and expected SHA-256 values; no lane or
  publication job may rebuild, regenerate, or restamp an artifact.
- The cohort manifest binds version, commit, tag, artifact paths/digests, build identity,
  and creation time. Result records bind those digests to platform, architecture, Python
  and client versions, acquisition source, command, exit status, relevant output,
  timestamp, and destination.
- Readiness blocks unless every required row for the current cohort passes. A newest
  unrelated manifest, skipped client, ambient executable, checkout import, or advisory
  failure is invalid evidence.
- Python proof covers wheel, sdist, companions, extras, `aeat`, and `cadrumo-mcp`.
  MCP proof launches the absolute installed executable and completes initialization,
  discovery, and a real calculation tool call.
- The command-bearing `cadrumo` distribution declares both exact-version data companions
  as mandatory runtime dependencies. Default, agent, all-extras, PyPI, Scoop, Homebrew,
  Claude plugin, and MCPB installs resolve the complete three-wheel cohort. There is no
  advertised slim-only CLI installation. Companion wheels remain separate files only
  for artifact-size limits; their individual claim is data integrity and namespace
  contribution, proved again by downstream cohort calculation.
- Functional acceptance uses one non-tautological installed-artifact oracle grounded in
  LIS Article 29 and the AEAT 2024 manual: a Modelo 200 2024 micro-enterprise taxable
  base of EUR 100,000 must produce `DP200014:00562 == 23000.00`. The probe uses isolated
  real encrypted storage and shipped registry data through public interfaces, never
  checkout imports, internal storage seeding, or duplicated business logic. It requires
  a persisted revision id, one target observation with the expected formula id and
  non-empty legal/source refs, and no ungrounded observation. The sole permitted warning
  is `modelo.work.calculate.plazo_vencido_unassessed_preview`; any other warning or error
  fails. Python/Scoop/Homebrew invoke installed `aeat`; MCP/Claude/MCPB invoke the real
  `cadrumo_modelo_work_calculate` tool. Help/version/startup alone cannot pass a lane.
- MCP/client execution must complete the public protocol sequence—profile creation,
  identity read after the profile-switch gate re-arms, work creation, and calculation—
  within the declared server timeout. A diagnostic or harness tool call is not a
  substitute. The retained result binds the installed server executable and cohort
  digest to the same oracle assertions as the direct CLI lane.
- The MCP server resolves the CLI executable from its own interpreter/installation and
  invokes that absolute path. It never calls bare `aeat` through ambient PATH. Acceptance
  scrubs checkout imports and unrelated executable paths, records both executable origins,
  and requires them to belong to the same installed cohort.
- Plugin proof validates the generated artifact, installs the complete marketplace-served
  plugin through a declared Claude client, observes MCP startup, and completes a
  cohort-pinned tool call.
- MCPB proof enforces signing/publisher policy, reconciles its Python requirement,
  installs through every claimed client, starts the server, and completes a tool call.
- Scoop proof uses versioned immutable URLs and hashes and supplies Windows wrappers or
  shims for both `aeat` and `cadrumo-mcp`. Clean Windows Sandbox exercises install,
  update/persistence behavior, both commands, the tax-work oracle, and an MCP calculation.
- Homebrew proof generates a versioned formula/tap snapshot with immutable URLs and
  hashes, a Homebrew Python dependency, and `Language::Python::Virtualenv` resources.
  Each claimed macOS/Linux row passes audit, from-source install, `brew test`, both
  installed commands, the tax-work oracle, and an MCP calculation.
- The support matrix names OS, architecture, Python, acquisition mechanism, client
  version, and behavior proved. Unexecuted rows are unsupported.
- Existing packaging and generation foundations are stable enough to reuse. Their
  evidence aggregation, client coverage, and publication boundaries are not stable
  enough to authorize release.

## Implementation

Create one immutable release-candidate cohort from a clean archive of the tagged commit.
A cohort manifest identifies every artifact and SHA-256 digest. Build completion freezes
the cohort; testing, staging, publication, verification, and documentation consume it
without mutation.

Real-behavior lanes install cohort artifacts into clean environments with checkout paths
removed. They execute installed CLI and MCP commands, exercise split-package behavior
and extras, and record cohort-bound evidence. Every applicable lane completes the same
grounded Modelo 200 tax-work oracle through its installed transport. Client lanes install
the generated Claude marketplace plugin and MCPB in declared supported clients, verify
server startup, and invoke the real calculation tool. Platform runners execute only
matrix rows the product intends to claim.

Replace the optional public corpus-source split with mandatory exact-version runtime
dependencies from `cadrumo` to both data companions. All channel generators install that
complete dependency closure. Replace MCP's ambient `aeat` subprocess with absolute
same-installation resolution. Add a negative real-behavior regression that launches the
installed server with unrelated PATH entries removed; the full protocol calculation must
still pass.

A generated Scoop manifest references immutable cohort release assets and hashes. Its
Windows package exposes both commands through explicit wrappers or shims. A clean Windows
Sandbox lane acquires from the intended bucket and invokes both installed commands,
including an MCP handshake and tool call.

A generated Homebrew formula and tap snapshot are cohort artifacts. The formula derives
pinned dependency resources from the locked graph, installs the application into an
isolated Homebrew-managed virtual environment, and links both entry points. Clean
macOS/Linux rows acquire it through the intended tap and pass `brew audit`, from-source
installation, `brew test`, the installed tax-work oracle, and MCP calculation.

A manually dispatched GitHub Actions release workflow, protected by the release
environment and using OIDC Trusted Publishing, is the sole publication authority. It
fetches the stored cohort, verifies manifest/hashes and the complete blocking evidence
set, and publishes those exact bytes. It never builds or generates. Marketplace, GitHub
release, MCPB, Scoop, Homebrew, root Python package, and companions are coordinated for
one version and cohort.

After publication, verification lanes acquire from the advertised PyPI, GitHub,
marketplace, MCPB, Scoop, and Homebrew paths and rerun installed behavior, including the
grounded tax-work oracle. README and user-doc
promotion is blocked until those records pass; beforehand the path is labelled
unavailable, staged, or source-only.

This decision supersedes the local-only and token-based publication rulings in the
accepted Claude ecosystem packaging ADR and amends the local-only publication ruling in
the release-readiness ADR. Their non-conflicting packaging, client, and readiness
decisions remain. GitHub Actions manual dispatch with OIDC becomes the sole release
publication authority; local recipes may build or diagnose candidates but may not upload
release artifacts.

## Rationale

The research proves local wheel, sdist, split-package, CLI, and MCP behavior can succeed,
while public acquisition is absent, client proof is incomplete, Scoop and Homebrew do
not exist, and current publication rebuilds outside the tested evidence chain. The reference
identifies reusable clean-source, installation, MCP-client, plugin-generation, and MCPB
foundations.

It also proves the current core manifest is a false readiness signal: a root wheel can
pass it while its installed CLI cannot create tax work because a tracked official corpus
file is absent. The exact three-wheel cohort passes both direct CLI and MCP calculations,
and MCP fails when ambient PATH is removed. Mandatory companions plus same-installation
subprocess resolution are therefore required, not optional hardening.

The immutable-cohort option uniquely keeps artifact identity constant from build through
acquisition. Blocking cohort-bound records turn support and availability into measured
facts. One manual GitHub Actions OIDC authority removes credential and rebuild ambiguity
while retaining an explicit human release decision.

## Consequences

- Released bytes gain traceable construction, installation, execution, acquisition,
  platform, and publication evidence.
- Broken or unavailable paths cannot be documented as generally available.
- Release duration and infrastructure cost increase, especially for split packages,
  Windows Sandbox, Homebrew on macOS/Linux, and real Claude client coverage.
- Client or platform outages block claims/releases requiring those rows; they cannot be
  converted to passing skips.
- Publication leaves developer workstations, reducing emergency flexibility but
  eliminating competing authorities.
- The first public release requires staged channel bootstrapping and delayed
  documentation promotion.
- Support scope becomes narrower but defensible: only measured matrix rows are supported.
- Scoop remains Windows-only; Homebrew, Python, and Claude surfaces carry independently
  proved platform claims.
