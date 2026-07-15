---
tags:
  - '#reference'
  - '#distribution-installation-readiness'
date: '2026-07-15'
modified: '2026-07-15'
related:
  - "[[2026-07-15-distribution-installation-readiness-research]]"
---

# `distribution-installation-readiness` reference: `Cohort build, install, execution, and promotion surfaces`

Pinned source snapshot: commit `5372d95f1bcaecf5fd79dc3dbe6ddb09aed3e27c`
on 2026-07-15. The reference covers packaging smoke runners, release readiness and
publication, Claude plugin and marketplace materialisation, installed MCP behavior,
MCPB construction, Python metadata, and the absent Scoop and Homebrew product surfaces.

## Summary

### One immutable release-candidate cohort must replace per-lane rebuilding

The real-behavior foundations are strong. Wheel construction, installation, and the
installed CLI live at `dev/packaging/smoke_core.py:607`,
`dev/packaging/smoke_core.py:620`, and `dev/packaging/smoke_core.py:781`.
Plain-pip and sdist installs reuse the installed probes at
`dev/packaging/smoke_pip_core.py:26`, `dev/packaging/smoke_pip_core.py:41`,
`dev/packaging/smoke_pip_core.py:98`, `dev/packaging/smoke_sdist_core.py:25`,
`dev/packaging/smoke_sdist_core.py:84`, and `dev/packaging/smoke_sdist_core.py:87`.
The split lane already supplies the right clean-source primitive by extracting
`git archive HEAD` at `dev/packaging/smoke_split_install.py:95-106`, then building and
testing all three wheels at `dev/packaging/smoke_split_install.py:113`,
`dev/packaging/smoke_split_install.py:159`, and
`dev/packaging/smoke_split_install.py:196-260`.

Generalise that primitive: one commit/tag produces the three wheels, sdist, plugin tree,
marketplace snapshot, MCPB, Scoop release material, and Homebrew tap/formula material
once. Every subsequent local,
platform, client, acquisition, and publish step consumes those exact paths after
SHA-256 verification. Observed 0.2.1 diagnostic artifact hashes are:

- latest root-wheel candidate: `f6b3a906d4b384856437d8f8d91af22bbd056c1c8cb3b6d0e49bb93a5f0b3756`;
- root sdist: `a41a100cd811acf6c79c7209160e0e1f3bb24180c832058d70647a34fa661413`;
- manuals wheel: `01afebcfc84fb4faf3583c299b2941242291815f021ba0b9482e310c30da8cf5`;
- official wheel: `ff46b27b758b8318c858d6e276a90d5430861047687275ab2b2def23b1a19e57`.

The command-bearing distribution must install all three wheels as one product. The
current optional split at `pyproject.toml:175-201` leaves default and `agent` installs
without required source binaries. The latest root wheel wrote an `ok: true` core
manifest, but its absolute installed CLI refused before work creation on a missing
tracked Modelo 289 official ZIP. Installing both exact-version companions made the
oracle pass. Move the companions into mandatory base/runtime dependencies and retire
public slim-only semantics; keep them as separate sub-100 MB files solely for index
limits. Test each companion's integrity and joined namespace, then test every
command-bearing installation with the complete cohort.

### The smoke manifest must become a cohort evidence contract

`dev/packaging/smoke_core.py:881-901` records only `ok`, lane, timestamp, work
directory, paths, checks, and optional details; `dev/packaging/tests/test_smoke_manifest.py:14-35`
pins that limited shape. It omits source commit/tag, cohort version, artifact digests,
platform and client identities, command transcript, and promotion destination. Each
lane independently rebuilds, including core at `dev/packaging/smoke_core.py:925`,
all-extras at `dev/packaging/smoke_extras.py:97`, and the browser/pip variants.

Make build output immutable and make every lane accept the cohort plus expected digests.
Append signed or otherwise tamper-evident result records for each platform/channel row;
never replace the cohort manifest with “latest manifest by modification time.”

### Installed behavior must include a grounded tax calculation

The strongest reusable oracle is the real Modelo 200 CLI scenario at
`src/cadrumo/entrypoints/cli/tests/test_modelo_calculation_through_real_cli.py:189-261`.
It drives the actual CLI and registry against isolated real storage and checks the
external LIS/AEAT oracle: taxable base EUR 100,000 produces
`DP200014:00562 == 23000.00` for a 2024 micro-enterprise. Extract the setup and assertion
into an installed-artifact probe that never imports from the checkout and never mirrors
the formula. Require Python, Scoop, and Homebrew launchers to pass it through installed
`aeat`; require MCP, Claude Code, and MCPB to pass the same work calculation through
`cadrumo_modelo_work_calculate`. Startup and identity checks remain prerequisites only.

The all-public CLI itinerary was reproduced against three fresh encrypted-storage roots.
With both M202 relation channels set to zero, the target observation is unique and carries
formula id `modelo-200-cuota-integra`, non-empty `legal_refs`, and non-empty `source_refs`;
no observation is ungrounded. The only warning is the expected historical-deadline code
`modelo.work.calculate.plazo_vencido_unassessed_preview`. The probe must whitelist that
exact code and reject any additional notice, error, missing persisted revision id,
different value/formula, missing grounding, or checkout import. Relevant public setup is
demonstrated at `src/cadrumo/entrypoints/cli/tests/test_modelo_200_stored_calculation_drift_cli.py:17-78`,
and the observation contract is defined at
`src/cadrumo/entrypoints/cli/_modelo_revision_payload_parts.py:38-70`.

### Installed MCP behavior belongs in packaging acceptance

Package metadata correctly owns `aeat` and `cadrumo-mcp` at `pyproject.toml:92-97`.
The reusable real-client oracle initializes, lists resources/prompts/tools, and calls
`cadrumo_harness_load` at `src/cadrumo/entrypoints/mcp/tests/test_client_handshake.py:57-84`,
but resolves `cadrumo-mcp` from ambient PATH at line 59. Add a clean wheel `[agent]`
lane using the absolute executable inside the target environment, scrubbed checkout
paths, and the full handshake/tool call. Correct the all-extras gate's case-sensitive
lowercase identity check at `dev/packaging/smoke_extras.py:57-68`; valid output is
uppercase `CADRUMO`.

The full protocol itinerary has been exercised through a real stdio SDK client against
the source environment: profile creation through `execute`, `cadrumo_whoami` after the
profile-switch gate re-armed, work creation through `execute`, and the complete Modelo
200 calculation through `execute`. It finished in 86.3 seconds inside the 120-second
mutation tier at `src/cadrumo/entrypoints/mcp/_call_runtime.py:35-55`. Promote that exact
flow into the installed-wheel lane; do not weaken it back to `cadrumo_harness_load`.

`src/cadrumo/entrypoints/mcp/_server.py:312` launches bare `aeat`. A scrubbed-PATH real
installed-server run fails with `[WinError 2]`, while a PATH restricted to the exact
three-wheel environment passes the full oracle. Replace ambient lookup with an absolute
interpreter-local/sibling console-script resolution and fail closed if it is absent.
The acceptance lane launches absolute installed `cadrumo-mcp`, removes checkout paths,
scrubs PATH of all unrelated Cadrumo executables, and proves both executables belong to
the same environment and cohort.

### Plugin and marketplace generation are the right authority but need boot proof

`src/cadrumo/agent/_workspace.py:353-404` emits plugin manifest, skills, agents, and
MCP configuration from one source. `src/cadrumo/agent/_workspace.py:409-458` delegates
the marketplace-served plugin to the same emitter. Preserve that boundary.

The generated bootstrap at `src/cadrumo/agent/_workspace.py:76-98` and
`src/cadrumo/agent/_workspace.py:353-363` is an external `uvx` acquisition. The validator
returns a successful `skipped` result without Claude at
`dev/packaging/smoke_plugin_validate.py:43-79`, and neither `justfile:247` nor
`.github/workflows/packaging-smoke.yml:49-69` includes it. Require strict validation on
a declared Claude-capable row, install the generated complete marketplace through the
real client, observe MCP startup, and call a cohort-pinned tool.

The generated `cadrumo[agent]` bootstrap also omits the two data companions. Publishing
it unchanged would still produce a clean server unable to perform the calculation.
Generation must target the complete mandatory product dependency cohort, and validation
must inspect the resolved distributions before the real client oracle runs.

Marketplace parity at `src/cadrumo/agent/tests/test_marketplace_generation.py:58-70`
is healthy, but drift protection at lines 73-78 compares only `marketplace.json`.
Byte-compare and publish the complete generated tree only after its bootstrap passes.

### MCPB remains an assembly artifact until a supported client runs it

`packaging/mcpb/build.py:21-29` explicitly excludes Desktop installation and publisher
verification. Lines 70-131 stamp the PyPI/uvx bootstrap, lines 161-172 create a
one-member archive, and lines 134-158 tolerate missing signing by emitting an unsigned
bundle. Put the MCPB in the cohort, require the selected signature policy, install it in
each claimed Desktop client, and prove its pinned server starts and completes a tool
call. Reconcile the manifest's Python `>=3.12` claim at
`packaging/mcpb/manifest.json:50-53` with `pyproject.toml:6` (`>=3.13`).

### Readiness and publication must consume the complete same-cohort proof

`dev/release/readiness.py:300-330` selects only the newest smoke manifest, accepts any
truthy lane, and treats missing or failed packaging evidence as advisory. Require every
promised platform/channel row for the current tag/commit and matching version/hashes;
absence or mismatch is blocking.

`.github/workflows/publish.yml:22-32`, `.github/workflows/publish.yml:52-62`, and
`.github/workflows/publish.yml:101` rebuild one distribution immediately before upload.
The local recipes separately rebuild root and companion artifacts at `justfile:710-737`
and `justfile:779-802`. Both violate tested-byte promotion. One coordinated versioned
publish must consume stored cohort files after digest verification.

Publication authority is contradictory. The accepted Claude ADR requires local,
human-gated publication and rejects Actions/OIDC at
`.vault/adr/2026-07-03-claude-ecosystem-packaging-adr.md:52-59` and lines 156-160.
The accepted readiness ADR also states local-only at
`.vault/adr/2026-07-04-release-readiness-gate-adr.md:29-32` and lines 122-129, while
the current workflow implements OIDC. The new ADR must choose one authority and
explicitly supersede the replaced publication rulings.

### Scoop and Homebrew are new architecture; platform support is measured, not inferred

No product Scoop manifest or bucket exists; `justfile:53-64` provisions contributor
tools only. Generate a versioned Scoop manifest pointing to immutable release assets,
pin SHA-256, define `aeat` and `cadrumo-mcp` shims plus persistence/update behavior,
then prove `scoop install` and both installed launchers inside a clean Windows Sandbox.
Scoop's official manifest contract downloads a pinned archive, checks its hash, extracts
it, and exposes `bin` shims; it is Windows-specific rather than evidence for other
platforms.

No formula or tap exists. Generate a Homebrew formula from the locked Python dependency
graph using immutable URLs and SHA-256 resource stanzas with
`Language::Python::Virtualenv`; install to `libexec` and link both executables. The
cohort-bound tap snapshot must pass `brew audit`, `brew install --build-from-source`,
`brew test`, the installed tax-work oracle, and installed MCP initialization/tool calls.
Homebrew's documented Python virtualenv pattern avoids modifying externally managed
site-packages, while its `test do` contract supplies an isolated temporary `HOME`.
Relevant upstream contracts are `https://docs.brew.sh/Python-for-Formula-Authors`,
`https://docs.brew.sh/Formula-Cookbook`, and
`https://docs.brew.sh/How-to-Create-and-Maintain-a-Tap`.

The current packaging workflow has one Ubuntu job at
`.github/workflows/packaging-smoke.yml:22-24`. Windows, macOS, architecture, Python,
Claude client, Homebrew, and MCPB claims require explicit cohort-bound rows.
Platform-neutral metadata is not a substitute for executed support.
