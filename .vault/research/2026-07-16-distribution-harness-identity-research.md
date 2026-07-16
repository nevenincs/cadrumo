---
tags:
  - '#research'
  - '#distribution-harness-identity'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
  - '[[2026-07-12-cadrumo-cli-executable-adr]]'
  - '[[2026-07-08-mcp-protocol-hardening-adr]]'
  - '[[2026-07-03-claude-ecosystem-packaging-adr]]'
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
---

# `distribution-harness-identity` research: `Distributed harness namespace and Model Context Protocol product-description identity`

This research checks whether the distribution-readiness architecture already makes
Cadrumo's bundled operating harness distinguishable from host or third-party harnesses.
It also checks whether the Model Context Protocol (MCP) product description reaches
users in English and Spanish. The review covers the authored harness, generated Claude
workspace and plugin layouts, marketplace and MCP Bundle (MCPB) metadata, protocol
discovery, real-client acceptance, and public reacquisition.

## Findings

### F1 - The harness source and generated Claude layouts expose generic identifiers

The seven authored personas, 34 skills, and seven rules use unprefixed names such as
`coordinator`, `preparar-modelo-200`, and `operator-grounding`. The generator preserves
those names when it copies skills, writes agent definitions, and writes rules. It also
derives each agent frontmatter name directly from the unprefixed persona filename. The
generated inventory, rather than a duplicated hand-authored list, must remain the count
and name authority as the harness evolves.

The relevant source locations are `src/cadrumo/_data/agent/personas`,
`src/cadrumo/_data/agent/skills`, `src/cadrumo/_data/agent/rules`, and
`src/cadrumo/agent/_workspace.py:269-282`, `297-372`, `608-634`. Existing generation
tests assert source-name equality, so they prove faithful copying but do not prove a
Cadrumo namespace. Generic installed names can collide with harness components supplied
by a user, another plugin, or the host.

### F2 - Product-level MCP identity is Cadrumo-branded, but the namespace is incomplete

The plugin name, MCP server name, executable, MCPB name, and MCPB display name already
derive from or spell the Cadrumo identity. The protocol server is created from
`PRODUCT_IDENTITY.mcp_server`. Generated plugin configuration uses the same canonical
source. These files define the values: `src/cadrumo/agent/_workspace.py:64-89`,
`401-417`, `src/cadrumo/entrypoints/mcp/_server.py:793`, and
`packaging/mcpb/manifest.json:4-7`.

The namespace is not complete in generated prompt and resource identifiers. Prompt
names and the final name segment of harness resource URIs retain unprefixed skill or
persona identifiers. Therefore a branded MCP server name does not prove that every
bundled harness identifier is distinguishable.

### F3 - The MCP product description is English-only and has multiple sources

The plugin generator has an English-only `_PLUGIN_DESCRIPTION`, the marketplace has an
English-only `_MARKETPLACE_DESCRIPTION`, and the MCPB manifest has English-only
`description` and `long_description` product copy. The relevant locations are
`src/cadrumo/agent/_workspace.py:70-78`, `128`, and
`packaging/mcpb/manifest.json:7-8`.

The formats expose plain string fields rather than one canonical description source.
Where a format has no locale map, its string must contain labeled English and Spanish
versions. Schema validation alone cannot prove that both versions contain the same
capability, safety, privacy, on-host storage, human confirmation, and never-files-live
claims.

This requirement applies to the user-facing MCP product or service description.
Operational tool, prompt, argument, and resource descriptions remain model-facing
English under the existing localization boundary unless a separate decision changes
that contract.

### F4 - Existing decisions require identity coherence and generated-output parity

The accepted active Cadrumo identity decision establishes the product, package, command,
MCP, plugin, and environment naming tuple. The accepted Claude-packaging decision
generates the plugin's skills and agents from one authored harness source. The accepted
distribution-readiness decision requires one immutable cohort and real installed-client
evidence before an artifact claim closes.

These decisions support a verification amendment. They do not currently state that
every harness identifier carries a `cadrumo-` prefix or that the MCP product description
must be bilingual.

### F5 - Verification must follow exact bytes through every delivery boundary

Source inspection alone cannot prove the user-visible result because generation,
archiving, installation, client discovery, publication, and reacquisition can each
change or omit metadata. The existing distribution plan already checks generated plugin
parity, MCPB construction, Claude Code, Claude Desktop, Cowork, public acquisition,
documentation claims, and the final artifact audit.

The new invariant should extend those checks with an inventory of emitted identifiers
and MCP product descriptions. Evidence records the cohort digest, artifact digest,
channel, client name and version, surface type, and observed identifier. It also records
both language versions and a verdict for each required product claim. Any unprefixed
harness identifier or English-only MCP product description remains an open delivery
defect.

## Options

- **Verify only the top-level product and server names.** This is inexpensive but
  leaves generic bundled skills, agents, rules, prompts, or resources
  indistinguishable.
- **Verify source names without inspecting artifacts or clients.** This detects
  authoring drift but cannot prove what users install and see.
- **Verify every delivery boundary.** Check the complete emitted namespace and MCP
  product description in authored data, generated artifacts, installed clients, public
  reacquisition, and the final audit.

The third option is the only one that verifies the user-facing claim. This research does not
authorize a rename or change artifact bytes. It identifies the acceptance invariant and
the evidence boundaries that must report current compliance.

## Unknowns

- Claude and MCPB schemas may differ in how they can carry locale-specific copy. Each
  implementation step must use the format's supported representation and retain both
  languages without inventing unsupported fields.
- Prefixing may affect existing skill routing, prompt names, resource URIs, persona
  selection, and client settings. This research does not choose a migration mechanism.
- A product reviewer must approve the Spanish wording against each required claim in
  the English MCP product description.
