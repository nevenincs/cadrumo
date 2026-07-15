---
tags:
  - '#research'
  - '#distribution-installation-readiness'
date: '2026-07-15'
modified: '2026-07-15'
related:
  - '[[2026-06-28-product-packaging-adr]]'
  - '[[2026-07-03-claude-ecosystem-packaging-adr]]'
  - '[[2026-07-04-release-readiness-gate-adr]]'
  - '[[2026-07-03-claude-ecosystem-packaging-close-honesty-review-audit]]'
---

# `distribution-installation-readiness` research: `Executable acquisition and installed-artifact proof`

This research tests the distribution system against one acceptance rule: a generated
artifact is approvable only when the artifact acquired through its advertised path is
installed and performs its claims. It covers the Python distributions, installed CLI
and MCP server, Claude plugin and marketplace, MCPB bundle, release promotion,
platform coverage, Scoop and Homebrew acquisition, and user-facing install guidance.

## Findings

### F1 - Public acquisition paths do not exist and current docs overstate availability

Anonymous checks on 2026-07-15 returned HTTP 404 for the PyPI JSON endpoints for
`cadrumo`, `cadrumo-data-manuals`, and `cadrumo-data-official`, and for the latest
GitHub release URL. The public `nevenincs/neve-marketplace` repository still serves
the former `aeat` plugin and launches `aeat-cli[agent]` / `aeat-mcp`; it has one commit
and no releases. The local marketplace source already describes `cadrumo`, so the
published marketplace is stale rather than absent.

`README.md:19-46` honestly limits installation to authorized source access. In
contrast, `docs/workstation-setup.md:21-31`, `docs/workstation-setup.md:125-152`,
`docs/how-to/connect-an-agent.md:26-57`, and `docs/updates.md:17-23` describe PyPI,
GitHub release, marketplace, and MCPB acquisition as available. Those instructions
cannot currently succeed for an outside user.

Source locators: `https://pypi.org/pypi/cadrumo/json`,
`https://pypi.org/pypi/cadrumo-data-manuals/json`,
`https://pypi.org/pypi/cadrumo-data-official/json`,
`https://github.com/nevenincs/cadrumo/releases/latest`,
`https://github.com/nevenincs/neve-marketplace`, `packaging/marketplace/README.md:1`.

### F2 - Existing build and isolated-install lanes are substantial, but the evidence contract is fragmented

Current 0.2.1 execution on 2026-07-15 produced these real results:

- `just packaging-smoke-dependencies`, `just packaging-smoke-source`, and
  `just packaging-smoke-preflight-tests` passed; 17,994 tracked shipped-data files
  were present and 15 preflight tests passed.
- `just packaging-smoke-core` built and installed the wheel into a fresh uv virtual
  environment and passed resource, attachment, optional-extra, and CLI/profile probes.
- `just packaging-smoke-pip-core` installed the wheel with plain pip and passed.
- `just packaging-smoke-sdist-core` built the sdist, installed it with plain pip build
  isolation, and passed.
- `just packaging-smoke-split` took 740 seconds but passed the complete three-wheel
  sequence. Slim-only installation produced the required loud remedy; installing the
  76.7 MB manuals and 62.5 MB official companion wheels removed the advisory and made
  byte-exact registry verification pass.

The manifests record lane name, relative artifacts, checks, timestamp, and Python
major/minor, but do not bind a complete cohort to one source commit/tag, SHA-256 set,
platform fingerprint, client version, command transcript, or promotion destination.
`dev/release/readiness.py:300-332` inspects only the newest manifest rather than a
required same-version cohort. `.github/workflows/publish.yml:52-101` rebuilds artifacts
instead of promoting the bytes already exercised. Therefore even a passing local
matrix does not prove the published bytes, once any exist.

The core lane is also behaviorally insufficient. A fresh candidate root wheel
(`f6b3a906d4b384856437d8f8d91af22bbd056c1c8cb3b6d0e49bb93a5f0b3756`) wrote
an `ok: true` core-wheel manifest after its installed profile/config probes. The same
wheel's absolute installed `aeat.exe` then failed at work creation because the registry
cited the absent tracked official source
`corpus/aeat_official/instructions/modelo_289/files/289_XSD_2.0_WSDL_2.0.1.zip`.
The file intentionally lives in the official data companion, while neither the base
dependencies nor `cadrumo[agent]` installs the companions.

Installing that root wheel with both companion wheels (manuals SHA-256
`01afebcfc84fb4faf3583c299b2941242291815f021ba0b9482e310c30da8cf5`, official
SHA-256 `ff46b27b758b8318c858d6e276a90d5430861047687275ab2b2def23b1a19e57`)
made the absolute installed CLI complete the full oracle in 83.3 seconds. The split
files are viable only as one required product installation cohort. A public slim-only
`cadrumo` install contradicts the executable-artifact criterion.

Source locators: `dev/packaging/smoke_core.py:781-960`,
`dev/packaging/smoke_pip_core.py:92-125`,
`dev/packaging/smoke_sdist_core.py:81-114`,
`dev/packaging/smoke_split_install.py:196-240`, `justfile:176-247`,
`.github/workflows/packaging-smoke.yml:49-69`, `pyproject.toml:144-201`.

### F3 - The installed MCP server works from a local wheel, but packaging CI does not prove it

A fresh CPython 3.13.11 environment installed the built
`cadrumo-0.2.1-py3-none-any.whl[agent]` by file path with checkout imports disabled.
A real MCP SDK client launched the installed absolute `cadrumo-mcp.exe`, initialized
server identity `cadrumo`, listed 8 tools, 35 prompts, and 48 resources, and called
`cadrumo_harness_load` successfully. This proves the local wheel's installed MCP
surface.

A second real stdio MCP client run against the current source environment then proved
the complete public protocol itinerary: `execute(config.profile.create)`, mandatory
`cadrumo_whoami`, `execute(modelo.work.create)`, and
`execute(modelo.work.calculate)`. It completed in 86.3 seconds under the server's real
120-second mutation timeout and returned the same persisted revision, EUR 23,000 target
observation, formula id, legal/source references, and sole historical-deadline warning
as the direct CLI probe. This proves the channel-neutral MCP calculation sequence and
safety gates, but not yet the combination of installed-wheel acquisition and that full
calculation in one retained cohort record.

An apparent installed-wheel full MCP success was subsequently invalidated. The MCP
dispatcher constructs subprocess argv as bare `aeat` at
`src/cadrumo/entrypoints/mcp/_server.py:312`, so it resolved the developer environment's
ambient executable rather than the wheel environment's CLI. Launching installed
`cadrumo-mcp.exe` by absolute path with `PATH` reduced to `C:\Windows\System32` made the
first real command fail with `[WinError 2]`. Restricting `PATH` instead to the exact
three-wheel cohort's Scripts directory plus System32 made the complete MCP oracle pass
in 77.5 seconds. The cohort is functional, but subprocess identity is unsafe: MCP must
resolve the CLI beside its own interpreter/console installation and never via ambient
PATH.

The checked-in handshake test instead launches the PATH-visible `cadrumo-mcp`, and the
main packaging recipes never run it from the installed wheel. The manual proof must be
promoted into a tracked cohort lane before release approval. It also cannot establish
PyPI or plugin acquisition while the package is unpublished.

Source locators: `src/cadrumo/entrypoints/mcp/tests/test_client_handshake.py:57-84`,
`src/cadrumo/entrypoints/mcp/_server.py:717-920`,
`src/cadrumo/entrypoints/mcp/_call_runtime.py:35-55`,
`src/cadrumo/entrypoints/mcp/_server.py:283-320`,
`justfile:176-247`, `.github/workflows/packaging-smoke.yml:49-69`.

### F4 - The all-extras gate contains identity drift

`just packaging-smoke-extras` installed the 0.2.1 wheel and all declared extras, then
failed because `_assert_cli_version` searches case-sensitively for `"cadrumo "` while
the correct installed CLI output is `CADRUMO 0.2.1`. The artifact started; the gate's
rename migration is incomplete. A release still fails because its required gate cannot
certify the correct product identity.

Source locator: `dev/packaging/smoke_extras.py:56-68`.

### F5 - Claude plugin proof stops at schema validation and its real bootstrap is broken

On Claude Code 2.1.210, a fresh generated plugin passed
`claude plugin validate --strict` and contained 34 skills and 7 agents. Validation is
only schema proof. `dev/packaging/smoke_plugin_validate.py:43-75` returns success with a
`skipped` status when Claude is unavailable and is not part of the aggregate packaging
or CI matrix.

The generated plugin and MCPB both launch `uvx --from cadrumo[agent]==0.2.1
cadrumo-mcp`. That exact command cannot acquire anything while the PyPI project is
absent. Even after publication it would install neither data companion because
`cadrumo[agent]` contains only MCP runtime dependencies and `corpus-sources` is a
separate extra; the resulting clean process cannot load the complete registry for tax
work. No retained evidence proves the current Cadrumo plugin was acquired from the
public marketplace, installed into Claude Code/Desktop/Cowork, booted its MCP server,
or completed a claimed tool call. The Claude ecosystem plan nevertheless marks those
operator-gated steps complete; its own close-honesty audit says they were deferred.

Source locators: `src/cadrumo/agent/_workspace.py`,
`dev/packaging/smoke_plugin_validate.py:1-95`, `packaging/mcpb/manifest.json:1`,
`pyproject.toml:144-201`,
`.vault/plan/2026-07-03-claude-ecosystem-packaging-plan.md:138-147`,
`.vault/audit/2026-07-03-claude-ecosystem-packaging-close-honesty-review-audit.md:76-100`.

### F6 - MCPB construction is real, but installability and publisher trust are unproven

The six MCPB build tests pass and the test file is formatter-clean. The builder and
tests prove manifest validation, version/bootstrap parity, and a one-member ZIP. They
explicitly exclude Desktop installation, signing identity, and publisher verification.
The current host has no `mcpb` executable, so neither signing nor a real client install
can be approved here. The manifest also claims Python `>=3.12` while the Python project
requires `>=3.13`, an authority mismatch to resolve.

Source locators: `packaging/mcpb/build.py:21-29`,
`packaging/mcpb/tests/test_build.py:37-57`,
`packaging/mcpb/tests/test_build.py:97-112`, `packaging/mcpb/manifest.json:1`,
`pyproject.toml:1-6`.

### F7 - Scoop is a developer prerequisite today, not a product distribution

No Cadrumo Scoop manifest or bucket layout exists. `justfile:53-64` uses Scoop only to
provision contributor workstation tools. Calling that a Scoop product path would be
false. A product Scoop surface is new architecture and must define the artifact it
installs, exact version/hash pinning, shims, persistence, update behavior, Windows
Sandbox installation, and installed CLI/MCP invocation. It must not be documented as
available until a real `scoop install` from the intended bucket succeeds and the
installed commands perform their claims.

Source locator: `justfile:53-64`.

### F8 - Homebrew is absent and must be generated as a real Python application formula

No Cadrumo formula or tap material exists. Homebrew's supported application pattern is a
formula with an exact source URL and SHA-256, a declared Homebrew Python dependency, and
`Language::Python::Virtualenv` with versioned dependency resources. The formula must
install the application into `libexec` and link its scripts so users receive both
`aeat` and `cadrumo-mcp` without writing into Homebrew's externally managed Python.

Homebrew requires a `test do` block that executes basic non-interactive functionality in
a temporary `HOME`, and its tap guidance recommends a real from-source install before
publishing. Structural Ruby validation is therefore insufficient. A generated formula
and tap snapshot must be cohort members, use immutable URLs and hashes, pass `brew audit`,
install with `brew install --build-from-source` on each claimed macOS/Linux row, run the
shared tax-work oracle through the installed `aeat`, and initialize/call the installed
`cadrumo-mcp`. Only the rows actually exercised may be documented as supported.

Source locators: `https://docs.brew.sh/Formula-Cookbook`,
`https://docs.brew.sh/Python-for-Formula-Authors`,
`https://docs.brew.sh/How-to-Create-and-Maintain-a-Tap`.

### F9 - Platform agnosticism must be a measured support matrix

This Windows host proves local Python 3.13 wheel/sdist/split/MCP behavior. It does not
prove Docker because the Docker daemon is unreachable, and it does not prove macOS or
Linux. Existing Docker code is real but retained evidence is version-stale relative to
0.2.1. Platform-neutral Python code and CI configuration are not execution evidence.

The acceptance matrix must name each promised operating system, architecture, Python
version, client version, acquisition mechanism, and supported command/tool call. A
surface remains unsupported or release-blocking until the same promoted cohort passes
there. Scoop is Windows-specific; Homebrew is proved independently on each claimed
macOS/Linux row; Python/PyPI, Claude plugin, and MCPB claims need their own applicable
platform rows.

Source locators: `dev/packaging/smoke_docker.py:208-222`,
`.github/workflows/packaging-smoke.yml:1-69`.

### F10 - A real tax calculation is the minimum behavioral acceptance oracle

The current packaging probes primarily prove resources, version output, imports, and
entry-point startup. Those are necessary but do not prove the installed product performs
its central claim. The real CLI integration suite already contains a non-tautological,
externally grounded Modelo 200 oracle: for tax year 2024, a micro-enterprise with a
EUR 100,000 taxable base produces casilla `DP200014:00562` of EUR 23,000 under the
23 percent rate in LIS Article 29 and the AEAT 2024 practical manual.

Promote this scenario into one channel-neutral installed-artifact probe. Python, Scoop,
and Homebrew lanes must invoke it through their installed `aeat`; MCP, Claude Code, and
MCPB lanes must invoke the corresponding real `cadrumo_modelo_work_calculate` MCP tool.
The complete public CLI itinerary was executed three times on 2026-07-15 against fresh
encrypted storage without internal seeding. Profile creation, work creation, and
calculation succeeded in 75.9-83.8 seconds. With both mutually exclusive Modelo 202
relation channels explicitly set to zero, the result contained exactly one observation
for `DP200014:00562`, value `23000.00`, formula id `modelo-200-cuota-integra`, five legal
references, and two source references including `aeat-modelo-200-manual-2024`. Every
observation carried legal and source grounding. The only envelope warning was the
expected `modelo.work.calculate.plazo_vencido_unassessed_preview` for the deliberately
historical 2024 filing period; there was no error.

The probe must therefore use isolated real storage and shipped registry data; assert the
exact value, unique target observation, formula identity, non-empty legal/source refs,
zero ungrounded observations, persisted revision id, and the exact enumerated advisory
set; and reject all other warnings. It may not import from the checkout, seed internal
storage, or reproduce calculation logic. Version/help, schema validation, handshake-only,
and harness-only checks remain prerequisites but cannot satisfy functional acceptance.

The experiments refine “artifact” into two roles. Command-bearing user installables
(Python/PyPI, Scoop, Homebrew, plugin bootstrap, and MCPB) must install the complete
three-wheel cohort and pass the tax oracle. The data-only companion wheels claim no
executable; each is accepted only as a cohort component after archive/data integrity,
namespace joining, exact-version dependency, and downstream calculation are proved.
They may not be documented as standalone product installs.

Source locators: `src/cadrumo/entrypoints/cli/tests/test_modelo_calculation_through_real_cli.py:189-261`,
`src/cadrumo/entrypoints/cli/tests/test_modelo_200_stored_calculation_drift_cli.py:17-78`,
`src/cadrumo/entrypoints/cli/_modelo_revision_payload_parts.py:38-70`,
`src/cadrumo/entrypoints/mcp/_dispatch.py:86-102`,
`src/cadrumo/entrypoints/mcp/tests/test_toolsets.py:43`.

### F11 - Distribution authority is contradictory

The accepted Claude ecosystem ADR chooses local human-gated token publication and
defers Trusted Publishing. The current publish workflow and release guide choose OIDC
Trusted Publishing, while live local token-publish recipes remain in `justfile`. No
superseding ADR was found. A single authority must own build, staging, evidence,
promotion, PyPI, companion packages, GitHub release, marketplace, MCPB, Scoop, and
Homebrew.

Source locators: `.vault/adr/2026-07-03-claude-ecosystem-packaging-adr.md`,
`.github/workflows/publish.yml:1-101`, `RELEASING.md:5-6`,
`RELEASING.md:170-173`, `justfile:705-834`.

## Decision frame

Three positions are coherent:

1. Keep the product source-only and correct every acquisition document to say so.
2. Build one immutable release-candidate cohort, test local artifact installation and
   execution, stage/acquire the same hashes through each intended channel, then promote
   those exact bytes and only then enable user-facing acquisition guidance.
3. Publish first and test the public result afterward, accepting exposure to immutable
   broken artifacts.

The second position matches the accepted architecture's intended acceptance gate and
the operator's executable-artifact rule. Each proof must record artifact source/URL,
   SHA-256, version, source commit/tag, full command and exit status, relevant stdout and
   stderr, platform/client versions, and timestamp. Construction, local installation,
   channel acquisition, installed execution, a grounded tax-work oracle, client execution,
   and documentation promotion are distinct gates; none substitutes for another.
