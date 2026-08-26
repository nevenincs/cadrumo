---
generated: true
tags:
  - '#index'
  - '#claude-ecosystem-packaging'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:989d41ea9c2ff3f1b2fb0ca6c8a836da8edea93a6f9216588e6714a44689ac3c'
related:
  - '[[2026-07-03-claude-ecosystem-packaging-adr]]'
  - '[[2026-07-03-claude-ecosystem-packaging-close-honesty-review-audit]]'
  - '[[2026-07-03-claude-ecosystem-packaging-code-review-audit]]'
  - '[[2026-07-03-claude-ecosystem-packaging-plan]]'
  - '[[2026-07-03-claude-ecosystem-packaging-research]]'
---

# `claude-ecosystem-packaging` feature index

Auto-generated index of all documents tagged with `#claude-ecosystem-packaging`.

## Documents

### adr

- `2026-07-03-claude-ecosystem-packaging-adr` - `claude-ecosystem-packaging` adr: `Claude ecosystem plugin as the first product distribution` | (**status:** `accepted`)

### audit

- `2026-07-03-claude-ecosystem-packaging-close-honesty-review-audit` - `claude-ecosystem-packaging` audit: `campaign close honesty review`
- `2026-07-03-claude-ecosystem-packaging-code-review-audit` - `claude-ecosystem-packaging` audit: `campaign code review`

### exec

- `2026-07-03-claude-ecosystem-packaging-W01-P01-S01` - Add an installed-vs-checkout detector and a platform user-data root resolver (LOCALAPPDATA on Windows, XDG_DATA_HOME on Linux, Application Support on macOS)
- `2026-07-03-claude-ecosystem-packaging-W01-P01-S02` - Root aeat_local_storage_root at the platform user-data directory for installed runs while preserving the PROJECT_ROOT var/storage default for a source checkout
- `2026-07-03-claude-ecosystem-packaging-W01-P01-S03` - Assert the derived tokens, logs, secret, blob and audit roots follow the installed platform base through the existing state-root validators
- `2026-07-03-claude-ecosystem-packaging-W01-P01-S04` - Prove installed-mode storage resolves off the platform directory and never off PROJECT_ROOT with a fresh-install roundtrip test
- `2026-07-03-claude-ecosystem-packaging-W01-P02-S05` - Demote vaultspec-rag[mcp] out of [project.dependencies] into the dev dependency group so a published product wheel carries no developer search tooling
- `2026-07-03-claude-ecosystem-packaging-W01-P02-S06` - Confirm deptry and the packaging-smoke dependency-surface gate stay clean after the demotion
- `2026-07-03-claude-ecosystem-packaging-W01-P02-S07` - Align the mcpb manifest license field from 'see repository' to the real Apache-2.0 SPDX expression
- `2026-07-03-claude-ecosystem-packaging-W02-P03-S08` - Exclude _data/corpus source binaries (*.pdf, *.xls, *.xlsx) from the aeat wheel via hatchling wheel excludes
- `2026-07-03-claude-ecosystem-packaging-W02-P03-S09` - Scaffold the aeat-data distribution build with its own pyproject reading the same source tree, force-including the corpus binaries under an aeat_data package with mirrored relative paths
- `2026-07-03-claude-ecosystem-packaging-W02-P03-S10` - Add a wheel-content test asserting the aeat wheel ships zero corpus pdf/xls/xlsx members while keeping the extracted-text, normative-html, registry and agent payload
- `2026-07-03-claude-ecosystem-packaging-W02-P03-S11` - Add a test that the aeat-data wheel packages exactly the corpus binaries under aeat_data with mirrored relative paths and nothing else
- `2026-07-03-claude-ecosystem-packaging-W02-P03-S12` - Keep the _data size-budget gate meaningful per distribution after the split so the budget is not evaded by moving bytes to the companion
- `2026-07-03-claude-ecosystem-packaging-W02-P04-S13` - Add a corpus-binary resolution seam that resolves a _data/corpus path from the aeat tree first, then the aeat_data companion package root
- `2026-07-03-claude-ecosystem-packaging-W02-P04-S14` - Test the seam resolves a corpus binary identically whether it lives under the aeat tree or the aeat_data companion root
- `2026-07-03-claude-ecosystem-packaging-W02-P05-S15` - Give verify_source_file a companion-aware absent branch: present binary stays byte-exact hash-enforced, absent-but-companion-declared binary returns an accumulable advisory rather than hard-failing
- `2026-07-03-claude-ecosystem-packaging-W02-P05-S16` - Make verify_source_catalogue accumulate absent companion binaries into one loud advisory naming the missing set and the aeat[corpus-sources] install hint
- `2026-07-03-claude-ecosystem-packaging-W02-P05-S17` - Make the four aeat app registry verification verbs refuse instructively when the companion is required and absent
- `2026-07-03-claude-ecosystem-packaging-W02-P05-S18` - Add an anti-tautology test that a corrupted PRESENT corpus binary still hard-fails the byte-exact hash gate
- `2026-07-03-claude-ecosystem-packaging-W02-P05-S19` - Add an anti-tautology test that an absent companion binary surfaces a loud advisory and is never silently accepted
- `2026-07-03-claude-ecosystem-packaging-W02-P06-S20` - Add the corpus-sources optional extra pinning aeat-data at an exact version
- `2026-07-03-claude-ecosystem-packaging-W02-P06-S21` - Add a split-install packaging-smoke lane proving the advisory path with the core wheel alone and the byte-identical path with the companion installed
- `2026-07-03-claude-ecosystem-packaging-W02-P06-S22` - Wire the split-install smoke lane into the just packaging-smoke recipe set
- `2026-07-03-claude-ecosystem-packaging-W03-P07-S23` - Add a plugin layout target that emits .claude-plugin/plugin.json with a kebab-case name, defaultEnabled false, an author object and the version read from installed package metadata
- `2026-07-03-claude-ecosystem-packaging-W03-P07-S24` - Emit the plugin skills/ tree (SKILL.md plus reference material) from the single authored harness source
- `2026-07-03-claude-ecosystem-packaging-W03-P07-S25` - Emit the plugin agents/ tree mapping persona frontmatter to Claude-native fields (tools/disallowedTools), never the non-Claude mode: field
- `2026-07-03-claude-ecosystem-packaging-W03-P07-S26` - Emit the plugin .mcp.json declaring the stdio aeat-mcp server launched via uvx aeat at a pinned version with AEAT_MCP_PERSONA wired from the userConfig persona interpolation
- `2026-07-03-claude-ecosystem-packaging-W03-P07-S27` - Declare the userConfig persona string option with a default in the plugin manifest, keeping server-side validation as the refusal surface
- `2026-07-03-claude-ecosystem-packaging-W03-P07-S28` - Test the plugin materialiser emits a schema-shaped plugin tree from the authored source with the persona and version correctly interpolated
- `2026-07-03-claude-ecosystem-packaging-W03-P08-S29` - Extend the aeat app agent CLI with a plugin layout target option selecting the plugin materialisation over the workspace layout
- `2026-07-03-claude-ecosystem-packaging-W03-P08-S30` - Add the typed result payload for the plugin materialisation summary emitted through the CLI envelope
- `2026-07-03-claude-ecosystem-packaging-W03-P08-S31` - Add a claude plugin validate --strict packaging gate that runs against a freshly materialised plugin when the claude CLI is on PATH and skips honestly when it is not (verify the validate flag against live official docs at execution time)
- `2026-07-03-claude-ecosystem-packaging-W03-P08-S32` - Test the CLI materialises a schema-valid plugin tree end-to-end to an output directory
- `2026-07-03-claude-ecosystem-packaging-W03-P09-S33` - Verify the mcp Python SDK annotation extension surface accepts the anthropic/requiresUserInteraction tool annotation before adopting it (frontier: confirm against the live mcp SDK and official docs)
- `2026-07-03-claude-ecosystem-packaging-W03-P09-S34` - Add the anthropic/requiresUserInteraction annotation to CONFIRM-tier (state-mutating) MCP tools alongside the existing destructiveHint matrix
- `2026-07-03-claude-ecosystem-packaging-W03-P09-S35` - Test the requiresUserInteraction annotation is present on every CONFIRM-tier tool and absent on read-only tools
- `2026-07-03-claude-ecosystem-packaging-W04-P10-S36` - Define the marketplace repository layout and a .claude-plugin/marketplace.json with name, owner and a plugins[] entry sourcing the aeat plugin tree (verify the marketplace.json schema against live official docs at execution time)
- `2026-07-03-claude-ecosystem-packaging-W04-P10-S37` - Have the plugin generator emit the marketplace-served plugin tree so marketplace and plugin cannot drift
- `2026-07-03-claude-ecosystem-packaging-W04-P10-S38` - Test the generator emits a schema-shaped marketplace tree whose plugins[] entry resolves to the emitted plugin
- `2026-07-03-claude-ecosystem-packaging-W04-P11-S39` - Add a LOCAL-ONLY HUMAN-GATED just publish recipe over uv publish with a scoped PyPI token, refusing to run in CI and mirroring the release-please discipline
- `2026-07-03-claude-ecosystem-packaging-W04-P11-S40` - Document the name-claim sequencing: publish the slim aeat wheel first (no grant needed) to claim the name
- `2026-07-03-claude-ecosystem-packaging-W04-P11-S41` - Document the aeat-data file-size grant request template and the publish-when-granted flow so the plugin delivery is not hard-blocked on the grant
- `2026-07-03-claude-ecosystem-packaging-W04-P11-S42` - Document the full release checklist joining versioning, wheel build, name claim, grant and plugin/marketplace push in RELEASING.md

### plan

- `2026-07-03-claude-ecosystem-packaging-plan` - `claude-ecosystem-packaging` plan

### research

- `2026-07-03-claude-ecosystem-packaging-research` - `claude-ecosystem-packaging` research: `Claude ecosystem as the first packaged product destination`
