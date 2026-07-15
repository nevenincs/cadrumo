---
tags:
  - '#plan'
  - '#distribution-installation-readiness'
date: '2026-07-15'
modified: '2026-07-15'
tier: L3
related:
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
  - '[[2026-07-15-distribution-installation-readiness-research]]'
  - '[[2026-07-15-distribution-installation-readiness-reference]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace distribution-installation-readiness with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries the AUTHORIZING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution Record artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorizing documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `distribution-installation-readiness` plan

## Wave `W01` - Make the Python product complete

Make the built Python cohort self-complete and establish one real installed tax-work oracle before any channel-specific work depends on it.

Build one immutable artifact cohort, install it through every claimed channel, perform
real grounded tax work, publish those exact bytes, and prove public reacquisition before
documenting availability.

### Phase `W01.P01` - Build one complete immutable cohort

Make the command-bearing distribution require its runtime data and generate one hash-bound cohort once from a clean tagged source archive.

- [ ] `W01.P01.S01` - Require exact-version manuals and official companions for every command-bearing install; `pyproject.toml`.
- [ ] `W01.P01.S02` - Lock the complete runtime dependency closure after metadata changes; `uv.lock`.
- [ ] `W01.P01.S03` - Build wheel sdist companions plugin MCPB Scoop and Homebrew members once from a clean archive; `dev/packaging/release_cohort.py`.
- [ ] `W01.P01.S04` - Define and validate the immutable cohort identity and digest contract; `dev/packaging/cohort_manifest.py`.
- [ ] `W01.P01.S05` - Prove cohort construction is deterministic complete and non-rebuilding; `dev/packaging/tests/test_release_cohort.py`.

### Phase `W01.P02` - Prove installed tax and MCP behavior

Create the shared real-behavior oracle and remove ambient checkout and PATH dependencies from installed CLI and MCP execution.

- [ ] `W01.P02.S06` - Execute the public CLI tax itinerary against isolated encrypted storage and assert the grounded Modelo 200 result; `dev/packaging/installed_tax_oracle.py`.
- [ ] `W01.P02.S07` - Execute the public MCP protocol itinerary and assert the same grounded Modelo 200 result; `dev/packaging/installed_mcp_oracle.py`.
- [ ] `W01.P02.S08` - Resolve the CLI subprocess from the MCP server installation instead of ambient PATH; `src/cadrumo/entrypoints/mcp/_server.py`.
- [ ] `W01.P02.S09` - Prove installed MCP execution succeeds with checkout imports and unrelated executable paths removed; `src/cadrumo/entrypoints/mcp/tests/test_installed_cli_resolution.py`.
- [ ] `W01.P02.S10` - Prove both installed commands originate from one environment and one cohort; `dev/packaging/tests/test_installed_oracles.py`.

## Wave `W02` - Generate every claimed distribution

Generate Python, Scoop, Homebrew, Claude plugin, marketplace, and MCPB artifacts from the same immutable cohort so later acceptance exercises one identity.

### Phase `W02.P03` - Harden Python artifacts

Make wheel, sdist, companion, default, agent, and all-extra installations consume and prove the complete cohort.

- [ ] `W02.P03.S11` - Make the core wheel lane install and exercise a supplied complete cohort; `dev/packaging/smoke_core.py`.
- [ ] `W02.P03.S12` - Make the plain pip lane consume supplied cohort artifacts without rebuilding; `dev/packaging/smoke_pip_core.py`.
- [ ] `W02.P03.S13` - Make the sdist lane consume the supplied cohort and verify its resolved companions; `dev/packaging/smoke_sdist_core.py`.
- [ ] `W02.P03.S14` - Make the split-install lane assert namespace integrity exact versions and downstream tax work; `dev/packaging/smoke_split_install.py`.
- [ ] `W02.P03.S15` - Correct the all-extras product identity gate and run real installed behavior; `dev/packaging/smoke_extras.py`.
- [ ] `W02.P03.S16` - Reject Python lane evidence that lacks the installed tax and MCP oracles; `dev/packaging/tests/test_packaging_real_behavior.py`.

### Phase `W02.P04` - Generate and prove Scoop

Create a versioned Scoop product artifact with both commands and exercise it in a clean Windows acquisition environment.

- [ ] `W02.P04.S17` - Generate a versioned Scoop manifest with immutable cohort URLs hashes persistence and both command shims; `packaging/scoop/generate.py`.
- [ ] `W02.P04.S18` - Prove Scoop generation matches the cohort and exposes both installed commands; `packaging/scoop/tests/test_generate.py`.
- [ ] `W02.P04.S19` - Install from the intended bucket in Windows Sandbox and execute CLI MCP update and persistence behavior; `dev/packaging/smoke_scoop.ps1`.
- [ ] `W02.P04.S20` - Run the clean Scoop acquisition gate on the declared Windows release row; `.github/workflows/packaging-scoop.yml`.

### Phase `W02.P05` - Generate and prove Homebrew

Create a pinned Python virtualenv formula and tap snapshot and exercise every platform row the formula claims.

- [ ] `W02.P05.S21` - Generate a pinned Python virtualenv formula and immutable tap snapshot from the cohort; `packaging/homebrew/generate.py`.
- [ ] `W02.P05.S22` - Prove Homebrew resources hashes Python requirement commands and test block match the cohort; `packaging/homebrew/tests/test_generate.py`.
- [ ] `W02.P05.S23` - Run audit source installation brew test CLI tax work and MCP tax work for one tap snapshot; `dev/packaging/smoke_homebrew.py`.
- [ ] `W02.P05.S24` - Run the Homebrew acquisition gate on every claimed macOS and Linux row; `.github/workflows/packaging-homebrew.yml`.

### Phase `W02.P06` - Generate and prove Claude artifacts

Bind plugin, marketplace, and MCPB generation to the complete cohort and require real client startup and tax-work tool calls.

- [ ] `W02.P06.S25` - Generate plugin bootstrap configuration that resolves the complete cohort; `src/cadrumo/agent/_workspace.py`.
- [ ] `W02.P06.S26` - Byte-compare the complete generated marketplace plugin tree with its source authority; `src/cadrumo/agent/tests/test_marketplace_generation.py`.
- [ ] `W02.P06.S27` - Install the marketplace-served plugin in Claude and require MCP startup plus a tax-work tool call; `dev/packaging/smoke_plugin_install.py`.
- [ ] `W02.P06.S28` - Align MCPB platform and Python requirements with the command-bearing distribution; `packaging/mcpb/manifest.json`.
- [ ] `W02.P06.S29` - Bind MCPB contents signing identity and bootstrap to the immutable cohort; `packaging/mcpb/build.py`.
- [ ] `W02.P06.S30` - Install MCPB through each claimed client and require the real tax-work tool call; `packaging/mcpb/tests/test_client_install.py`.

## Wave `W03` - Prove platforms and clients

Run cohort-bound acceptance on declared operating systems and real clients, with missing or skipped behavior treated as unsupported rather than passing.

### Phase `W03.P07` - Aggregate cohort evidence

Replace fragmented lane manifests with a schema that binds source, hashes, environment, commands, results, and destinations to one cohort.

- [ ] `W03.P07.S31` - Record cohort source digests runtime platform client command transcript result and destination; `dev/packaging/evidence.py`.
- [ ] `W03.P07.S32` - Require a complete same-cohort evidence set in release readiness; `dev/release/readiness.py`.
- [ ] `W03.P07.S33` - Reject stale skipped ambient mismatched and incomplete release evidence; `dev/release/tests/test_distribution_readiness.py`.

### Phase `W03.P08` - Execute the support matrix

Run clean platform and client rows against exact cohort hashes and reject absent, skipped, ambient, or mismatched execution evidence.

- [ ] `W03.P08.S34` - Execute the complete cohort and installed tax oracle on the claimed Linux Python row; `.github/workflows/packaging-smoke.yml`.
- [ ] `W03.P08.S35` - Execute the complete cohort and installed tax oracle on the claimed Windows Python row; `.github/workflows/packaging-smoke.yml`.
- [ ] `W03.P08.S36` - Execute the complete cohort and installed tax oracle on the claimed macOS Python row; `.github/workflows/packaging-smoke.yml`.
- [ ] `W03.P08.S37` - Execute Homebrew installation and both real-behavior oracles on the claimed Linux row; `.github/workflows/packaging-homebrew.yml`.
- [ ] `W03.P08.S38` - Install the cohort plugin in Claude Code and execute the real tax-work tool call; `.github/workflows/packaging-claude.yml`.
- [ ] `W03.P08.S39` - Install the cohort plugin or MCPB in Claude Desktop and execute the real tax-work tool call; `.github/workflows/packaging-claude.yml`.
- [ ] `W03.P08.S40` - Install the supported artifact in Cowork and execute the real tax-work tool call; `.github/workflows/packaging-claude.yml`.

## Wave `W04` - Promote and reacquire exact bytes

Publish only the tested cohort through one authority, then reacquire from every advertised channel and repeat installed behavior before availability is claimed.

### Phase `W04.P09` - Promote without rebuilding

Make the protected manual OIDC workflow consume stored tested artifacts and remove competing publication paths.

- [ ] `W04.P09.S41` - Promote stored cohort bytes through protected manual OIDC publication without rebuilding; `.github/workflows/publish.yml`.
- [ ] `W04.P09.S42` - Verify cohort hashes evidence completeness and destination versions before any upload; `dev/release/readiness.py`.
- [ ] `W04.P09.S43` - Remove local release upload authority while retaining diagnostic build recipes; `justfile`.
- [ ] `W04.P09.S44` - Prove the publish workflow cannot build regenerate or accept unrelated artifacts; `dev/release/tests/test_publish_workflow.py`.

### Phase `W04.P10` - Reacquire public channels

Install from the actual public endpoints and repeat both command and tax-work behavior before promotion is accepted.

- [ ] `W04.P10.S45` - Acquire root and companion distributions from PyPI and repeat installed CLI and MCP tax work; `dev/packaging/acquire_pypi.py`.
- [ ] `W04.P10.S46` - Acquire the exact GitHub release cohort and verify every retained digest; `dev/packaging/acquire_github_release.py`.
- [ ] `W04.P10.S47` - Acquire Cadrumo through the public Scoop bucket and repeat installed behavior; `dev/packaging/acquire_scoop.ps1`.
- [ ] `W04.P10.S48` - Acquire Cadrumo through the public Homebrew tap and repeat installed behavior; `dev/packaging/acquire_homebrew.py`.
- [ ] `W04.P10.S49` - Acquire the public marketplace plugin through Claude and repeat the MCP tax-work call; `dev/packaging/acquire_claude_plugin.py`.
- [ ] `W04.P10.S50` - Acquire the published MCPB through each claimed client and repeat the MCP tax-work call; `dev/packaging/acquire_mcpb.py`.

## Wave `W05` - Document measured reality and close

Publish acquisition guidance only for passing channels, formally review the implementation, and retain an auditable mapping from every claim to executable evidence.

### Phase `W05.P11` - Write acquisition documentation

Align README and user guides with the measured support matrix and prevent documentation from leading artifact availability.

- [ ] `W05.P11.S51` - Define the installation guide information architecture and evidence-backed claim boundaries; `docs/_distribution-installation-wireframe.md`.
- [ ] `W05.P11.S52` - Publish only currently proven acquisition commands and support claims; `README.md`.
- [ ] `W05.P11.S53` - Document clean installation verification update and removal for Python Scoop and Homebrew; `docs/workstation-setup.md`.
- [ ] `W05.P11.S54` - Document Claude Code Desktop Cowork plugin and MCPB acquisition with real verification commands; `docs/how-to/connect-an-agent.md`.
- [ ] `W05.P11.S55` - Publish the measured platform client and channel support matrix; `docs/updates.md`.
- [ ] `W05.P11.S56` - Fail documentation checks when an advertised channel lacks matching acquisition evidence; `dev/docs/tests/test_distribution_claims.py`.

### Phase `W05.P12` - Review and audit delivery

Run feature-scoped quality, architecture, documentation, and honest-close reviews with execution records for every completed step.

- [ ] `W05.P12.S57` - Run the path-scoped formatting tests and vault checks for every touched implementation surface; `.vault/exec/2026-07-15-distribution-installation-readiness`.
- [ ] `W05.P12.S58` - Perform a formal safety intent and quality review of the finished distribution implementation; `.vault/audit/2026-07-15-distribution-installation-readiness-code-review-audit.md`.
- [ ] `W05.P12.S59` - Audit every generated artifact claim against retained installed behavior and public reacquisition evidence; `.vault/audit/2026-07-15-distribution-installation-readiness-close-audit.md`.
- [ ] `W05.P12.S60` - Create step execution records rebuild the feature index and close only evidenced rows; `.vault/index/distribution-installation-readiness.index.md`.

## Description

This plan converts executable-artifact behavior from an informal expectation into a
blocking delivery contract. It begins by making the Python product complete and by
extracting one channel-neutral tax-work oracle. It then generates every distribution
surface from one cohort, executes each claimed platform and client, promotes without
rebuilding, reacquires from public endpoints, and publishes only claims supported by
retained evidence.

Construction, schema validation, help output, startup, and source-tree tests remain
useful prerequisites. None can close a command-bearing artifact Step without clean
installation and successful tax work through that artifact's public interface. A data
companion closes only when its integrity, exact-version participation, namespace
contribution, and downstream cohort calculation are proved.

## Steps

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorizing documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

Waves are ordered. `W01` establishes the dependency closure, cohort identity, and
behavioral oracle required everywhere else. Within `W02`, Python hardening precedes
channel bootstraps, while Scoop, Homebrew, and Claude generation may proceed independently
after the cohort contract stabilizes. `W03` begins only when the corresponding `W02`
artifact exists. Independent platform and client rows may execute concurrently against
the same hashes. `W04` requires the complete blocking matrix; public reacquisition begins
only after each destination receives the exact cohort. Documentation drafting in `W05`
may prepare against retained evidence, but availability language cannot land until the
matching reacquisition Step passes.

## Verification

- One clean tagged source archive produces one complete cohort manifest whose recorded
  SHA-256 digests remain unchanged through testing, publication, and reacquisition.
- Default, agent, all-extra, wheel, and sdist installation resolves the same exact root,
  manuals, and official distribution versions without checkout imports.
- Installed `aeat` completes the Modelo 200 2024 oracle and reports
  `DP200014:00562 == 23000.00` with the required formula, legal references, source
  references, persisted revision, and diagnostic constraints.
- Installed `cadrumo-mcp` resolves the CLI from its own environment, completes the public
  protocol itinerary, and returns the same grounded tax result with unrelated PATH and
  checkout entries removed.
- Scoop and Homebrew installations expose both commands and pass their real-behavior
  oracles on every support row actually claimed.
- Claude plugin, marketplace, and MCPB installations start their cohort-pinned server in
  each claimed real client and complete the tax-work tool call; missing clients and skips
  cannot pass.
- Publication consumes stored artifacts and evidence without any build or regeneration
  command, and every advertised endpoint can reacquire the recorded hashes.
- README and user documentation name only acquisition paths, platforms, and clients with
  passing post-public evidence.
- Feature-scoped tests and Vault checks pass, formal review reports no unresolved blocking
  finding, every checked Step has an execution record, and the plan reports no open Step.
