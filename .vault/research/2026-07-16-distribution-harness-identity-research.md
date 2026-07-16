---
tags:
  - '#research'
  - '#distribution-harness-identity'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - "[[2026-07-15-distribution-installation-readiness-adr]]"
  - "[[2026-07-12-cadrumo-product-rename-adr]]"
  - "[[2026-07-03-claude-ecosystem-packaging-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #research) and one feature tag.
     Replace distribution-harness-identity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `distribution-harness-identity` research: `Distributed harness namespace and MCP description identity`

This research checks whether the distribution-readiness architecture already makes
Cadrumo's bundled operating harness distinguishable from host or third-party harnesses.
It also checks whether the Model Context Protocol (MCP) product description reaches
users in English and Spanish. The review covers the authored harness, generated Claude
workspace and plugin layouts, marketplace and MCP Bundle (MCPB) metadata, protocol
discovery, real-client acceptance, and public reacquisition.

## Findings

### F1 - The authored harness and generated Claude layouts expose generic identifiers

The authored personas, skills, and rules use unprefixed names such as `coordinator`,
`preparar-modelo-200`, and `operator-grounding`. The generator preserves those names
when it copies skills, writes agent definitions, and writes rules. It also derives each
agent frontmatter name directly from the unprefixed persona filename.

The relevant authorities are `src/cadrumo/_data/agent/personas`,
`src/cadrumo/_data/agent/skills`, `src/cadrumo/_data/agent/rules`, and
`src/cadrumo/agent/_workspace.py:269-282`, `297-372`, `608-634`. Existing generation
tests assert source-name equality, so they prove faithful copying but do not prove a
Cadrumo namespace. Generic installed names can collide with harness components supplied
by a user, another plugin, or the host.

### F2 - Product-level MCP identity is Cadrumo-branded, but the namespace is incomplete

The plugin name, MCP server name, executable, MCPB name, and MCPB display name already
derive from or spell the Cadrumo identity. The protocol server is created from
`PRODUCT_IDENTITY.mcp_server`, and generated plugin configuration uses the same
authority. These surfaces are grounded at `src/cadrumo/agent/_workspace.py:64-89`,
`401-417`, `src/cadrumo/entrypoints/mcp/_server.py:793`, and
`packaging/mcpb/manifest.json:4-7`.

The namespace is not complete at client-visible MCP surfaces. The MCPB declares generic
tools named `search` and `execute`, while prompts and harness resources also retain
unprefixed skill or persona identities. Therefore a branded server name does not prove
that every bundled harness identifier is distinguishable.

### F3 - MCP product descriptions are English-only and have multiple authorities

The plugin generator has an English-only `_PLUGIN_DESCRIPTION`, the marketplace has an
English-only `_MARKETPLACE_DESCRIPTION`, and the MCPB manifest has English-only
`description`, `long_description`, configuration descriptions, and tool descriptions.
The relevant locations are `src/cadrumo/agent/_workspace.py:70-78`, `128`, `208-217`,
and `packaging/mcpb/manifest.json:7-8`, `29-53`.

The formats expose plain string fields rather than one shared locale-aware description
authority. Where a format has no locale map, an equivalent English and Spanish pair
must be represented in the supported string shape. A passing schema validator cannot
establish translation presence or semantic parity.

### F4 - Existing decisions require identity coherence and generated-output parity

The accepted product-rename decision establishes one Cadrumo identity across MCP,
plugins, generated outputs, multilingual copy, and release artifacts. The accepted
Claude-packaging decision generates the plugin's skills and agents from one authored
harness source. The accepted distribution-readiness decision requires one immutable
cohort and real installed-client evidence before an artifact claim closes.

These decisions support a verification amendment. They do not currently state that
every harness identifier carries a `cadrumo-` prefix or that the MCP product description
must be bilingual.

### F5 - Verification must follow exact bytes through every delivery boundary

Source inspection alone cannot prove the user-visible result because generation,
archiving, installation, client discovery, publication, and reacquisition can each
change or omit metadata. The existing distribution plan already has gates for generated
plugin parity, MCPB construction, Claude Code, Claude Desktop, Cowork, public
marketplace acquisition, published MCPB acquisition, documentation claims, and final
artifact audit.

The new invariant should extend those gates with an inventory of exact emitted
identifiers and descriptions. Evidence must name the cohort digest, artifact, channel,
client version, observed identifier, English description, Spanish description, and
pass or failure result. Any unprefixed harness identifier or English-only MCP
description remains an open delivery defect.

## Options

1. Verify only the top-level product and server names. This is inexpensive but leaves
   generic bundled skills, agents, rules, prompts, resources, or tools indistinguishable.
2. Verify all source names without inspecting artifacts or clients. This detects authoring
   drift but cannot prove what users install and see.
3. Verify the full emitted namespace and bilingual description across authored data,
   generated artifacts, installed clients, public reacquisition, and final audit. This
   matches the immutable-cohort evidence model and exposes migration work before a
   channel is approved.

Option 3 is the only option that verifies the user-facing claim. This research does not
authorize a rename or change artifact bytes. It identifies the acceptance invariant and
the evidence boundaries that must report current compliance.

## Unknowns

- Claude and MCPB schemas may differ in how they can carry locale-specific copy. Each
  implementation step must use the format's supported representation and retain both
  languages without inventing unsupported fields.
- Prefixing may affect existing skill routing, prompt names, resource URIs, persona
  selection, and client settings. This research does not choose a migration mechanism.
- The required Spanish wording needs product review for semantic parity with the
  approved English safety and privacy claims.
