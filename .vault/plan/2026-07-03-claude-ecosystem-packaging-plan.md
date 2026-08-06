---
tags:
  - '#plan'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:16d3561250ae08dc5be893e4261c149ee94b7846ba14393031c2652f9064b410'
tier: L3
related:
  - '[[2026-07-03-claude-ecosystem-packaging-adr]]'
  - '[[2026-07-03-claude-ecosystem-packaging-research]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
  - '[[2026-07-15-distribution-installation-readiness-plan]]'
---

<!-- RETIRED: S43, S44, S45, S46, S47 -->

# `claude-ecosystem-packaging` plan

Ship the aeat CLI plus the aeat-mcp harness as the first real product install: a slim published wheel, a corpus-binaries companion, and a one-click Claude plugin verified end to end on a real client.

## Current authority note (2026-07-16)

This plan is retained as execution history, not as the current distribution
contract. The accepted
`[[2026-07-15-distribution-installation-readiness-adr]]` and its plan preserve
the physical wheel split, plugin, marketplace, and integrity-boundary work, but
retire the `corpus-sources` optional extra, the supported root-only/advisory
installation mode, and local token publication. Current command-bearing
installs require both exact-version data companions, and release promotion
consumes one immutable fully tested cohort through the sole protected OIDC
authority. Completed steps below record what this campaign implemented at the
time; they do not override that later authority.

## Wave `W01` - Product-run foundations

Make an installed run safe and lean before any distribution work: move the storage state root off the in-package PROJECT_ROOT to a platform user-data directory for installed runs (checkout default preserved), demote the developer-only vaultspec-rag search stack out of the base dependency set, and align the stale mcpb manifest license field. Largely independent of Wave W03; no downstream Wave hard-depends on it, but it gates a publishable, honest first release.

### Phase `W01.P01` - Platform user-data storage root for installed runs

Resolve the installed-run storage state root to a platform user-data directory while preserving the checkout default for the dev loop, so the derived tokens, logs, secret, blob and audit roots follow and no encrypted store lands inside a virtualenv or uv cache.

- [x] `W01.P01.S01` - Add an installed-vs-checkout detector and a platform user-data root resolver (LOCALAPPDATA on Windows, XDG_DATA_HOME on Linux, Application Support on macOS); `src/aeat/core/_config_state_root.py`.
- [x] `W01.P01.S02` - Root aeat_local_storage_root at the platform user-data directory for installed runs while preserving the PROJECT_ROOT var/storage default for a source checkout; `src/aeat/core/config.py`.
- [x] `W01.P01.S03` - Assert the derived tokens, logs, secret, blob and audit roots follow the installed platform base through the existing state-root validators; `src/aeat/core/tests/test_config_state_root.py`.
- [x] `W01.P01.S04` - Prove installed-mode storage resolves off the platform directory and never off PROJECT_ROOT with a fresh-install roundtrip test; `src/aeat/core/tests/test_config_state_root.py`.

### Phase `W01.P02` - Dependency and manifest hygiene

Demote the developer-only vaultspec-rag search stack out of the base dependency set and align the stale mcpb manifest license field, so a published product wheel carries no dev tooling and states its real Apache-2.0 license.

- [x] `W01.P02.S05` - Demote vaultspec-rag[mcp] out of [project.dependencies] into the dev dependency group so a published product wheel carries no developer search tooling; `pyproject.toml`.
- [x] `W01.P02.S06` - Confirm deptry and the packaging-smoke dependency-surface gate stay clean after the demotion; `dev/packaging/dependency_surface.py`.
- [x] `W01.P02.S07` - Align the mcpb manifest license field from 'see repository' to the real Apache-2.0 SPDX expression; `packaging/mcpb/manifest.json`.

## Wave `W02` - Wheel split and integrity-gate tolerance

Historical campaign scope: split the single 171.8 MB wheel into a slim runtime
file plus companion data files with mirrored paths, add a corpus locator
resolution seam that reads either root, and make the always-on registry
integrity gate companion-aware. The successor keeps the physical split and
byte-exact enforcement but requires every command-bearing installation to
resolve the full cohort.

### Phase `W02.P03` - Two-distribution wheel split build config

Exclude the corpus source binaries from the aeat wheel and package exactly those binaries in a new aeat-data distribution with mirrored relative paths, keeping the single source tree and the data-budget gate intact.

- [x] `W02.P03.S08` - Exclude _data/corpus source binaries (*.pdf, *.xls, *.xlsx) from the aeat wheel via hatchling wheel excludes; `pyproject.toml`.
- [x] `W02.P03.S09` - Scaffold the aeat-data distribution build with its own pyproject reading the same source tree, force-including the corpus binaries under an aeat_data package with mirrored relative paths; `packaging/aeat_data/pyproject.toml`.
- [x] `W02.P03.S10` - Add a wheel-content test asserting the aeat wheel ships zero corpus pdf/xls/xlsx members while keeping the extracted-text, normative-html, registry and agent payload; `src/aeat/tests/test_wheel_content_boundary.py`.
- [x] `W02.P03.S11` - Add a test that the aeat-data wheel packages exactly the corpus binaries under aeat_data with mirrored relative paths and nothing else; `dev/packaging/tests/test_aeat_data_distribution.py`.
- [x] `W02.P03.S12` - Keep the _data size-budget gate meaningful per distribution after the split so the budget is not evaded by moving bytes to the companion; `src/aeat/tests/test_data_size_budget.py`.

### Phase `W02.P04` - Corpus locator resolution seam

Add a resolution seam to the bundled-data locator that tries the aeat tree first then the aeat_data companion, so full-checkout and split-install corpus reads are uniform.

- [x] `W02.P04.S13` - Add a corpus-binary resolution seam that resolves a _data/corpus path from the aeat tree first, then the aeat_data companion package root; `src/aeat/core/resources/_boundary.py`.
- [x] `W02.P04.S14` - Test the seam resolves a corpus binary identically whether it lives under the aeat tree or the aeat_data companion root; `src/aeat/core/resources/tests/test_corpus_companion_seam.py`.

### Phase `W02.P05` - Companion-aware integrity gate

Give the registry source-verification gate the companion-aware absent branch: present binaries stay byte-exact hash-enforced, absent-but-companion-declared binaries accumulate into one loud advisory with the install hint, and the registry verification verbs refuse instructively, with anti-tautology proofs.

- [x] `W02.P05.S15` - Give verify_source_file a companion-aware absent branch: present binary stays byte-exact hash-enforced, absent-but-companion-declared binary returns an accumulable advisory rather than hard-failing; `src/aeat/domain/calculations/registry/_corpus_catalogue.py`.
- [x] `W02.P05.S16` - Make verify_source_catalogue accumulate absent companion binaries into one loud advisory naming the missing set and the aeat[corpus-sources] install hint; `src/aeat/domain/calculations/registry/_corpus_catalogue.py`.
- [x] `W02.P05.S17` - Make the four aeat app registry verification verbs refuse instructively when the companion is required and absent; `src/aeat/entrypoints/cli/registry.py`.
- [x] `W02.P05.S18` - Add an anti-tautology test that a corrupted PRESENT corpus binary still hard-fails the byte-exact hash gate; `src/aeat/domain/calculations/registry/tests/test_corpus_catalogue_companion.py`.
- [x] `W02.P05.S19` - Add an anti-tautology test that an absent companion binary surfaces a loud advisory and is never silently accepted; `src/aeat/domain/calculations/registry/tests/test_corpus_catalogue_companion.py`.

### Phase `W02.P06` - historical corpus-sources extra and split-install smoke lane

Historical scope: add the corpus-sources extra and prove both the root-only
diagnostic and complete split installation. The optional extra and supported
root-only mode are now retired.

- [x] `W02.P06.S20` - Add the historical corpus-sources optional extra pinning aeat-data at an exact version; `pyproject.toml`.
- [x] `W02.P06.S21` - Add a split-install packaging-smoke lane proving the advisory path with the core wheel alone and the byte-identical path with the companion installed; `dev/packaging/smoke_split_install.py`.
- [x] `W02.P06.S22` - Wire the split-install smoke lane into the just packaging-smoke recipe set; `justfile`.

## Wave `W03` - Plugin generation

Extend the aeat app agent materialiser and CLI with a Claude plugin layout target: .claude-plugin/plugin.json (defaultEnabled false, version from package metadata), skills/ and agents/ from the single authored harness source with Claude-native frontmatter mapping, an .mcp.json launching aeat-mcp via uvx aeat at a pinned version with the persona wired through userConfig, claude plugin validate --strict as a gate, and the anthropic/requiresUserInteraction annotation hardening CONFIRM-tier tools. Largely independent of Wave W01; produces the artifact Wave W04 publishes.

### Phase `W03.P07` - Plugin layout target in the materialiser

Extend the workspace materialiser with a plugin layout target emitting the plugin manifest, skills, agents with Claude-native frontmatter, and the MCP server declaration from the single authored harness source.

- [x] `W03.P07.S23` - Add a plugin layout target that emits .claude-plugin/plugin.json with a kebab-case name, defaultEnabled false, an author object and the version read from installed package metadata; `src/aeat/agent/_workspace.py`.
- [x] `W03.P07.S24` - Emit the plugin skills/ tree (SKILL.md plus reference material) from the single authored harness source; `src/aeat/agent/_workspace.py`.
- [x] `W03.P07.S25` - Emit the plugin agents/ tree mapping persona frontmatter to Claude-native fields (tools/disallowedTools), never the non-Claude mode: field; `src/aeat/agent/_workspace.py`.
- [x] `W03.P07.S26` - Emit the plugin .mcp.json declaring the stdio aeat-mcp server launched via uvx aeat at a pinned version with AEAT_MCP_PERSONA wired from the userConfig persona interpolation; `src/aeat/agent/_workspace.py`.
- [x] `W03.P07.S27` - Declare the userConfig persona string option with a default in the plugin manifest, keeping server-side validation as the refusal surface; `src/aeat/agent/_workspace.py`.
- [x] `W03.P07.S28` - Test the plugin materialiser emits a schema-shaped plugin tree from the authored source with the persona and version correctly interpolated; `src/aeat/agent/tests/test_plugin_workspace.py`.

### Phase `W03.P08` - Plugin CLI target and validation gate

Surface the plugin layout through the aeat app agent CLI and make claude plugin validate --strict a packaging gate where the CLI is available.

- [x] `W03.P08.S29` - Extend the aeat app agent CLI with a plugin layout target option selecting the plugin materialisation over the workspace layout; `src/aeat/entrypoints/cli/_app_agent_workspace.py`.
- [x] `W03.P08.S30` - Add the typed result payload for the plugin materialisation summary emitted through the CLI envelope; `src/aeat/entrypoints/cli/_app_agent_workspace_payloads.py`.
- [x] `W03.P08.S31` - Add a claude plugin validate --strict packaging gate that runs against a freshly materialised plugin when the claude CLI is on PATH and skips honestly when it is not (verify the validate flag against live official docs at execution time); `dev/packaging/smoke_plugin_validate.py`.
- [x] `W03.P08.S32` - Test the CLI materialises a schema-valid plugin tree end-to-end to an output directory; `src/aeat/entrypoints/cli/tests/test_app_agent_plugin.py`.

### Phase `W03.P09` - CONFIRM annotation hardening

Adopt the anthropic/requiresUserInteraction annotation on CONFIRM-tier MCP tools after verifying the mcp SDK annotation extension surface, making the human gate bypass-proof in Claude clients.

- [x] `W03.P09.S33` - Verify the mcp Python SDK annotation extension surface accepts the anthropic/requiresUserInteraction tool annotation before adopting it (frontier: confirm against the live mcp SDK and official docs); `src/aeat/entrypoints/mcp/_annotations.py`.
- [x] `W03.P09.S34` - Add the anthropic/requiresUserInteraction annotation to CONFIRM-tier (state-mutating) MCP tools alongside the existing destructiveHint matrix; `src/aeat/entrypoints/mcp/_annotations.py`.
- [x] `W03.P09.S35` - Test the requiresUserInteraction annotation is present on every CONFIRM-tier tool and absent on read-only tools; `src/aeat/entrypoints/mcp/tests/test_annotations.py`.

## Wave `W04` - Marketplace and release lane

Stand up the distribution surface: a dedicated marketplace repository layout with marketplace.json that the generator emits alongside the plugin tree it serves, and LOCAL-ONLY, HUMAN-GATED just publish recipes over uv publish with a scoped token extending the accepted release-please discipline, including the name-claim sequencing (slim wheel first, no grant) and the aeat-data file-size grant request and publish-when-granted flow, documented in RELEASING.md. Depends on Wave W02 (the split must build and the gate must tolerate absence before publishing).

### Phase `W04.P10` - Marketplace repository layout

Define the marketplace repository layout and marketplace.json, and have the generator emit the plugin tree the marketplace serves.

- [x] `W04.P10.S36` - Define the marketplace repository layout and a .claude-plugin/marketplace.json with name, owner and a plugins[] entry sourcing the aeat plugin tree (verify the marketplace.json schema against live official docs at execution time); `packaging/marketplace/marketplace.json`.
- [x] `W04.P10.S37` - Have the plugin generator emit the marketplace-served plugin tree so marketplace and plugin cannot drift; `src/aeat/agent/_workspace.py`.
- [x] `W04.P10.S38` - Test the generator emits a schema-shaped marketplace tree whose plugins[] entry resolves to the emitted plugin; `src/aeat/agent/tests/test_marketplace_generation.py`.

### Phase `W04.P11` - Publish recipes and release sequencing

Historical implementation: add LOCAL-ONLY HUMAN-GATED just publish recipes over
uv publish plus a scoped token, the name-claim and aeat-data grant sequencing,
and the RELEASING.md checklist. The successor ADR retires this publication
authority in favour of immutable tested-cohort OIDC promotion.

- [x] `W04.P11.S39` - Add a LOCAL-ONLY HUMAN-GATED just publish recipe over uv publish with a scoped PyPI token, refusing to run in CI and mirroring the release-please discipline; `justfile`.
- [x] `W04.P11.S40` - Document the name-claim sequencing: publish the slim aeat wheel first (no grant needed) to claim the name; `RELEASING.md`.
- [x] `W04.P11.S41` - Document the aeat-data file-size grant request template and the publish-when-granted flow so the plugin delivery is not hard-blocked on the grant; `RELEASING.md`.
- [x] `W04.P11.S42` - Document the full release checklist joining versioning, wheel build, name claim, grant and plugin/marketplace push in RELEASING.md; `RELEASING.md`.

## Wave `W05` - Live-client verification

The acceptance gate: a real-client install proof from the marketplace into Claude Code CLI (the confirmed floor), Claude Desktop, and Cowork (resolving the cloud-vs-local MCP execution question), and the golden regularizar-atrasos itinerary run end-to-end through the installed plugin per the R7 live-measurement harness, closing with a recorded verified support matrix. Depends on every prior Wave and gates campaign close. Steps needing a real PyPI account, token, or a live client install are operator-gated.

The checkboxes in this historical wave record the campaign's proof artifacts,
not current public-acquisition acceptance. The close-honesty audit retained the
operator-gated live-client and first-publication gaps, and the successor plan
owns their executable cohort-bound closure.

### Phase `W05.P12` - Real-client install proof

Install the plugin from the marketplace into Claude Code CLI, Claude Desktop, and Cowork, resolving the cloud-vs-local MCP execution question; operator-gated where a real client or account is required.

### Phase `W05.P13` - Golden itinerary and support matrix

Run the golden regularizar-atrasos itinerary end-to-end through the installed plugin per the R7 harness and record the verified support matrix the userdocs will state.

## Description

The product has zero user-facing distribution today: nothing is published to any
index, the `aeat` PyPI name is unclaimed, and the shipped `.mcpb` bundle is a
dead pointer that assumes `aeat-mcp` is already on the machine. This plan
delivers the full distribution chain the accepted ADR decided: a slim published
`aeat` wheel, an `aeat-data` companion carrying the corpus source binaries, a
Claude plugin generated from the single authored harness source, a marketplace
and a local human-gated publish lane, and a real-client install proof as the
acceptance gate.

The work was grounded in the ADR's four decision axes and the research findings.
D1c forced the physical wheel split: the corpus source binaries are 94% of the wheel's
weight (research F8) yet serve only the always-on registry integrity hash chain
and the opt-in `aeat app registry` verification verbs at runtime (F10), so a
grant-free slim wheel of roughly 36 MB decouples the plugin delivery from PyPI's
SLA-less file-size grant queue. The successor decision keeps the split but makes
all three files one mandatory command-bearing installation. Every present
binary stays byte-exact hash-enforced, and an absent required companion is an
incomplete-install refusal rather than a supported advisory mode. D2a picks `uvx aeat` at a pinned
version as the bootstrap for machines with Node but no Python. D3a makes the
Claude plugin the consumer vehicle (superseding the harness-refoundation R8
`.mcpb`), generated by re-targeting the existing `aeat app agent` materialiser.
D4a's local publication ruling was implemented historically and is now
superseded by the successor ADR's sole protected OIDC promotion authority.

A blocking product-run defect is fixed first: `Settings.aeat_local_storage_root`
defaults to `PROJECT_ROOT / var / storage`, which under an installed wheel
resolves inside the virtualenv and under `uvx` inside uv's ephemeral cache, where
the taxpayer's encrypted store could be wiped by a cache prune. The installed
default moves to a platform user-data directory while the checkout default stays
for the dev loop. Every regulatory value, safety rail, and provenance contract
from the parent ADRs carries over unchanged: never-live-submit, evidence bytes
never off-host, the bundled-corpus verification chain, and the CONFIRM human gate
(now hardened with the `anthropic/requiresUserInteraction` annotation).

Several plugin, marketplace, and MCP-annotation schemas named here are July-2026
frontier surfaces (research F9). Every Step that consumes one of those field
names carries an explicit sub-check to verify it against live official docs at
execution time rather than trusting the plan text, and the live-client install
proof - not documentation reading - is the acceptance gate.

## Parallelization

Waves W01 and W03 are largely independent and may run in parallel: W01
(product-run foundations) touches `core/config.py`, `pyproject.toml`, and the
mcpb manifest, while W03 (plugin generation) touches the `agent/_workspace.py`
materialiser, the agent CLI, and the MCP annotations. Neither hard-depends on
the other. W02 (wheel split and integrity tolerance) also has no hard dependency
on W01 or W03 and can proceed alongside them, but it gates W04: the release lane
must not publish until the slim wheel builds, the `aeat-data` companion packs the
binaries, and the integrity gate tolerates absence honestly. W04 (marketplace and
release lane) therefore begins only after W02 lands and consumes the plugin
artifact W03 produces. W05 (live-client verification) is the terminal Wave: it
depends on every prior Wave and gates campaign close.

Within Waves, the phases parallelize where they share no file. In W02, the build
config (P03), the resolution seam (P04), and the integrity gate (P05) touch
distinct files and can be developed concurrently, though P06's split-install
smoke lane needs P03 and P05 in place to exercise both the advisory and
byte-identical paths. In W03, the materialiser phase (P07) must land before the
CLI target (P08) that surfaces it; the CONFIRM hardening (P09) is independent of
both. Inside a phase, the `_workspace.py` emission Steps (S23 through S27) share
one file and are sequential; the paired test Steps follow their implementation.
Every Step that edits a shared file must re-read HEAD and abort on non-authored
WIP before its first edit, per the shared-worktree discipline.

The W05 install-proof and itinerary Steps that need a real PyPI account, a scoped
token, or a live Claude Desktop / Cowork install are operator-gated and cannot be
completed autonomously; they carry explicit operator instructions in their Step
Records.

## Verification

The plan is complete when every Step is closed and each carries a Step Record
with a passing gate. The load-bearing acceptance criteria:

- W01: `uv run --no-sync pytest src/aeat/core/tests/test_config_state_root.py`
  proves an installed-mode storage root resolves off the platform user-data
  directory and never off `PROJECT_ROOT`, and the checkout default is unchanged;
  `just packaging-smoke-dependencies` and `deptry` are clean after the
  `vaultspec-rag` demotion; the mcpb manifest carries the Apache-2.0 SPDX
  expression.
- W02 historical proof: a real `uv build` of the `aeat` wheel ships zero corpus `.pdf`/`.xls`/
  `.xlsx` members (verified by `test_wheel_content_boundary.py`) while keeping the
  extracted-text, normative-html, registry, and agent payload; the `aeat-data`
  wheel packages exactly those binaries under `aeat_data` with mirrored paths; the
  resolution seam resolves a binary from either root; the integrity gate keeps
  every present binary byte-exact (a corrupted present binary still hard-fails)
  and historically surfaced a loud, never-silent advisory for an absent
  companion binary. Current acceptance instead requires every command-bearing
  install to resolve both exact-version companions and treats absence as an
  incomplete-install failure; the
  `_data` size-budget gate stays meaningful per distribution; the split-install
  smoke lane proves both the advisory path (core alone) and the byte-identical
  path (with companion).
- W03: the plugin materialiser emits a schema-shaped `.claude-plugin/plugin.json`
  (defaultEnabled false, version from package metadata), `skills/`, `agents/` with
  Claude-native frontmatter (no `mode:`), and an `.mcp.json` launching
  `uvx aeat@<pinned>` with the persona wired from `userConfig`; `claude plugin
  validate --strict` passes where the CLI is available; every CONFIRM-tier tool
  carries the `anthropic/requiresUserInteraction` annotation and read-only tools
  do not.
- W04 historical proof: the generator emits a schema-shaped marketplace tree
  whose `plugins[]` entry resolves to the emitted plugin. The local publish
  recipe evidence is historical; the successor plan owns the immutable-cohort
  OIDC release proof.
- W05 (acceptance gate): the plugin installs from the marketplace into the Claude
  Code CLI and the local `aeat-mcp` server runs; the Claude Desktop and Cowork
  install proofs are recorded (operator-gated) resolving the cloud-vs-local MCP
  question; the golden `regularizar-atrasos` itinerary runs end to end through the
  installed plugin per the R7 harness; the verified support matrix is recorded and
  is what the userdocs state.

Every frontier-surface Step (plugin.json, .mcp.json, marketplace.json,
`claude plugin validate`, the MCP annotation) is verified against live official
docs at execution time; the plan text is not trusted as the schema authority.
