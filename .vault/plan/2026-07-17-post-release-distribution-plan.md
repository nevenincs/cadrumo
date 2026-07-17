---
tags:
  - '#plan'
  - '#post-release-distribution'
date: '2026-07-17'
modified: '2026-07-17'
tier: L2
related:
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
  - '[[2026-07-16-distribution-harness-identity-adr]]'
  - '[[2026-07-15-distribution-installation-readiness-plan]]'
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
     Replace post-release-distribution with a kebab-case feature tag, e.g. #foo-bar.
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

# `post-release-distribution` plan

### Phase `P01` - Prove local channel artifacts in real acquisition environments

Exercise the generated Scoop, Homebrew, and MCPB artifacts in the real clean-acquisition environments they target. Every step here needs multi-OS runner or real-publisher access unavailable from this development worktree.


<!-- One-line headline summary plan. -->

- [ ] `P01.S01` - Install from the intended bucket in Windows Sandbox and execute CLI, MCP, update, and persistence behavior (lifted from distribution W02.P04.S19); `dev/packaging/smoke_scoop.ps1`.
- [ ] `P01.S02` - Run the clean Scoop acquisition gate on the declared Windows release row (lifted from distribution W02.P04.S20); `.github/workflows/packaging-scoop.yml`.
- [ ] `P01.S03` - Run the Homebrew acquisition gate on every claimed macOS and Linux row (lifted from distribution W02.P05.S24); `.github/workflows/packaging-homebrew.yml`.
- [ ] `P01.S04` - Bind MCPB contents signing identity and bootstrap to the immutable cohort (lifted from distribution W02.P06.S29, needs a real publisher signing identity); `packaging/mcpb/build.py`.

### Phase `P02` - Execute the platform and client support matrix

Run cohort-bound installed-behavior oracles on every claimed operating-system row and inside every real Claude client. Every step needs multi-OS CI runners and real Claude-client installs unavailable from this worktree.

- [ ] `P02.S05` - Execute the complete cohort and installed tax oracle on the claimed Linux Python row (lifted from distribution W03.P08.S34); `.github/workflows/packaging-smoke.yml`.
- [ ] `P02.S06` - Execute the complete cohort and installed tax oracle on the claimed Windows Python row (lifted from distribution W03.P08.S35); `.github/workflows/packaging-smoke.yml`.
- [ ] `P02.S07` - Execute the complete cohort and installed tax oracle on the claimed macOS Python row (lifted from distribution W03.P08.S36); `.github/workflows/packaging-smoke.yml`.
- [ ] `P02.S08` - Execute Homebrew installation and both real-behavior oracles on the claimed Linux row (lifted from distribution W03.P08.S37); `.github/workflows/packaging-homebrew.yml`.
- [ ] `P02.S09` - Install the cohort plugin in Claude Code and execute the real tax-work tool call (lifted from distribution W03.P08.S38); `.github/workflows/packaging-claude.yml`.
- [ ] `P02.S10` - Install the cohort plugin or MCPB in Claude Desktop and execute the real tax-work tool call (lifted from distribution W03.P08.S39); `.github/workflows/packaging-claude.yml`.
- [ ] `P02.S11` - Install the supported artifact in Cowork and execute the real tax-work tool call (lifted from distribution W03.P08.S40); `.github/workflows/packaging-claude.yml`.
- [ ] `P02.S12` - Capture each real Claude client harness identifier inventory, MCP server name, and English and Spanish MCP product descriptions and compare them with the exact cohort (lifted from distribution W03.P08.S69); `.github/workflows/packaging-claude.yml, var/distribution-install-readiness`.

### Phase `P03` - Promote and reacquire the public channels

Publish the tested cohort through the protected workflow and reacquire the exact bytes from every advertised public endpoint. Blocked by held operator publish approval and by public-registry reacquisition access.

- [ ] `P03.S13` - Promote stored cohort bytes through protected manual OIDC publication without rebuilding (lifted from distribution W04.P09.S41, blocked by held operator publish approval); `.github/workflows/publish.yml`.
- [ ] `P03.S14` - Acquire root and companion distributions from PyPI and repeat installed CLI and MCP tax work (lifted from distribution W04.P10.S45); `dev/packaging/acquire_pypi.py`.
- [ ] `P03.S15` - Acquire the exact GitHub release cohort and verify every retained digest (lifted from distribution W04.P10.S46); `dev/packaging/acquire_github_release.py`.
- [ ] `P03.S16` - Acquire Cadrumo through the public Scoop bucket and repeat installed behavior (lifted from distribution W04.P10.S47); `dev/packaging/acquire_scoop.ps1`.
- [ ] `P03.S17` - Acquire Cadrumo through the public Homebrew tap and repeat installed behavior (lifted from distribution W04.P10.S48); `dev/packaging/acquire_homebrew.py`.
- [ ] `P03.S18` - Acquire the public marketplace plugin through Claude and repeat the MCP tax-work call (lifted from distribution W04.P10.S49); `dev/packaging/acquire_claude_plugin.py`.
- [ ] `P03.S19` - Acquire the published MCPB through each claimed client and repeat the MCP tax-work call (lifted from distribution W04.P10.S50); `dev/packaging/acquire_mcpb.py`.
- [ ] `P03.S20` - Reacquire every public Claude artifact and verify its cadrumo- harness namespace and English and Spanish MCP product descriptions against the cohort manifest (lifted from distribution W04.P10.S70); `dev/packaging/acquire_claude_plugin.py, dev/packaging/acquire_mcpb.py`.

### Phase `P04` - Publish availability documentation and audit against public evidence

Write availability language and the support matrix only for channels with passing post-public evidence, and audit every artifact claim against retained installed-behavior and public-reacquisition evidence. Blocked until the reacquisition evidence exists.

- [ ] `P04.S21` - Publish only currently proven acquisition commands and support claims (lifted from distribution W05.P11.S52); `README.md`.
- [ ] `P04.S22` - Document clean installation, verification, update, and removal for Python, Scoop, and Homebrew (lifted from distribution W05.P11.S53); `docs/workstation-setup.md`.
- [ ] `P04.S23` - Document Claude Code, Desktop, and Cowork plugin and MCPB acquisition with real verification commands (lifted from distribution W05.P11.S54); `docs/how-to/connect-an-agent.md`.
- [ ] `P04.S24` - Publish the measured platform, client, and channel support matrix (lifted from distribution W05.P11.S55); `docs/updates.md`.
- [ ] `P04.S25` - Audit every generated artifact claim against retained installed behavior and public reacquisition evidence (lifted from distribution W05.P12.S59); `.vault/audit/2026-07-17-post-release-distribution-close-audit.md`.

## Description

This plan holds the tail of the distribution-installation-readiness campaign that cannot be completed from this development worktree. The parent campaign built and locally proved every generated artifact: the cohort manifest, the Python wheel and sdist lanes, the Scoop and Homebrew generators, the plugin, marketplace, and MCPB artifacts, and the release-readiness evidence schema. What remains is the work that requires real external access, and it is gated on two conditions that this worktree cannot satisfy.

The first gate is operator publish-workflow approval. Publication is currently HELD by the operator until the worktree is declared settled, so promoting the cohort through the protected manual OIDC workflow (P03.S13) cannot proceed. No agent may flip that gate; only the operator can.

The second gate is real public-registry and multi-operating-system access. Reacquiring the exact published bytes from PyPI, the GitHub release, the public Scoop bucket, the public Homebrew tap, the Claude marketplace, and the MCPB clients (all of P03) needs those registries to have received the promoted cohort first and needs credentialled reacquisition. Executing the platform and client support matrix (all of P02) needs multi-OS CI runners and real Claude Code, Claude Desktop, and Cowork client installs. Proving the local channel artifacts in their target environments (all of P01) needs Windows Sandbox, multi-OS acquisition-gate runners, and a real publisher signing identity for MCPB. Writing availability documentation and auditing the artifact claims (all of P04) can only assert channels that already have passing post-public evidence, which does not yet exist.

Every step in this plan was lifted verbatim from the distribution-installation-readiness plan and its originating step identifier is recorded in each row. None is checked. The completable local remainder stays in the parent plan for the distribution peer to finish; this plan is the honest home for the deferred work so the parent can close its local scope without falsely completing what only the post-release environment can prove.

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

The phases are ordered by the release lifecycle and cannot be freely parallelized. P01 proves the local channel artifacts in their target acquisition environments; P02 executes the platform and client support matrix against those artifacts; P03 promotes the tested cohort and reacquires it from public endpoints; P04 documents and audits only channels with passing post-public evidence. P03 cannot begin until the operator lifts the publish hold, and P04 cannot begin until P03 has produced reacquisition evidence. Within each phase, the individual operating-system and client rows are mutually independent and may run concurrently on separate runners once that phase's gate is open.

## Verification

- Every Scoop, Homebrew, and MCPB artifact installs and runs its real-behavior oracle in its target clean-acquisition environment (Windows Sandbox and the multi-OS acquisition-gate runners), and the MCPB signing identity binds to the immutable cohort.
- The installed tax oracle reports the grounded Modelo 200 result on every claimed Linux, Windows, and macOS Python row, and the Claude Code, Claude Desktop, and Cowork clients each start the cohort-pinned server and complete the tax-work tool call; a missing client or a skip cannot pass.
- Publication consumes the stored cohort without any build or regeneration, and every advertised public endpoint reacquires the recorded SHA-256 digests and repeats installed behavior.
- README and user documentation name only acquisition paths, platforms, and clients with passing post-public evidence, and the close audit maps every artifact claim to retained installed-behavior and public-reacquisition evidence.
- The plan is complete only when every step above is closed against real external evidence; a fresh-context honesty review runs against the closure summary before completion is declared.
