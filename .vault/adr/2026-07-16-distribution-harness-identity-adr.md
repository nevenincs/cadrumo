---
tags:
  - '#adr'
  - '#distribution-harness-identity'
date: '2026-07-16'
modified: '2026-07-17'
body_hash: 'sha256:7a7e4815ed059adcab93912ce4b0f609fb48e04b4c2503fb8d499b6ec62ee03c'
related:
  - '[[2026-07-16-distribution-harness-identity-research]]'
  - '[[2026-07-15-distribution-installation-readiness-adr]]'
  - '[[2026-07-12-cadrumo-cli-executable-adr]]'
  - '[[2026-07-08-mcp-protocol-hardening-adr]]'
  - '[[2026-07-03-claude-ecosystem-packaging-adr]]'
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
---

# `distribution-harness-identity` adr: `Cadrumo-prefixed harness namespace and bilingual Model Context Protocol product description` | (**status:** `accepted`)

## Problem statement

Cadrumo distributes one authored operating harness through wheel data, Claude
workspaces, plugins, marketplace artifacts, Model Context Protocol (MCP) resources and
prompts, and MCP Bundles (MCPBs). Its agent/persona, skill, and rule identifiers are
generic. The authored tree exposes names such as `coordinator`,
`preparar-modelo-200`, and `operator-grounding`; the materialiser preserves them in
client-visible paths and agent frontmatter.

A persona is the authored harness role. Claude materialisation emits that persona as an
agent definition, so both surfaces must carry the same prefixed identity.

Generic harness identifiers can collide with host, user, or third-party components.
They also hide which package supplied an installed capability. Top-level MCP identity is
already Cadrumo-owned, but plugin, marketplace, and MCPB product descriptions are
English-only or derive from separate English-only sources.

Delivery needs one blocking acceptance invariant spanning the exact authored,
generated, installed, published, and reacquired bytes. This decision adds that
verification invariant to distribution readiness. It does not authorize a rename,
translation wording, compatibility alias, or artifact mutation.

## Considerations

- A harness identifier is every client-visible or materialised name for a bundled
  persona, generated agent definition, skill, rule, or its prompt and resource copy.
- Persona, generated agent, skill, and rule identities use the literal `cadrumo-` prefix in
  filenames, directories, frontmatter, and their prompt or resource projections.
- MCP identity follows the accepted Cadrumo tuple in each surface's grammar.
  `cadrumo`, `cadrumo-mcp`, `cadrumo_`, and `cadrumo://` are compliant Cadrumo
  prefixes; this decision does not mechanically replace them with hyphenated forms.
- Every user-facing MCP product description requires equivalent English and Spanish
  text across plugin, marketplace, MCPB, and claimed-client display metadata. A
  single-string schema carries both languages in a schema-supported representation.
- This requirement does not localize model-facing operational tool, prompt, argument,
  or resource descriptions. Their existing English-only contract remains unchanged.
- Generic progressive-discovery tools such as `search`, `execute`, `toolsets`, and
  `describe` are MCP operations, not projected harness document identifiers. Their
  accepted names remain unchanged.
- Translation parity includes the capability, safety, privacy, on-host storage, human
  confirmation, and never-files-live claims. Two language labels alone cannot pass.
- Identity parity means equality between the authored inventory and the metadata
  observed after generation, installation, publication, and public reacquisition.
- Source inspection and schema validation do not prove installed client presentation.

## Considered options

- **Verify only the top-level product and MCP server names.** Rejected because those
  names do not distinguish bundled agents, skills, rules, prompts, or resources.
- **Verify only the authored source.** Rejected because later delivery stages can omit
  or transform identity and copy.
- **Verify every delivery boundary.** Chosen because exact release artifacts and real
  clients prove what users install and see.
- **Rename noncompliant surfaces now.** Rejected because migration mechanics,
  translations, routing changes, and client compatibility need separate approval.

## Constraints

The accepted MCP-relevant subset of the Cadrumo identity tuple remains stable:

- human executable: `aeat`
- MCP server identifier: `cadrumo`
- MCP executable: `cadrumo-mcp`
- tool prefix: `cadrumo_`
- resource Uniform Resource Identifier (URI) scheme: `cadrumo://`
- plugin identifier: `cadrumo`

This amendment creates no alias, executable, plugin identifier, tool prefix, resource
scheme, or server identity.

The accepted harness and distribution decisions also remain stable. One harness source
feeds the minimum MCP tool surface, resources, prompts, Claude materialisation, and
packaged artifacts. The Claude plugin remains the primary consumer distribution. MCPB
remains secondary, and immutable tested-cohort promotion remains the release path.

Spanish-stem naming remains binding. `cadrumo-` is an outer product qualifier; it does
not translate or replace an established workflow stem.

Verification retains the cohort digest, artifact digest, channel, client name and
version, surface type, observed identifier, and expected identifier. It also retains
the English and Spanish MCP product descriptions. Each required capability, safety,
privacy, on-host storage, human confirmation, and never-files-live claim receives a
verdict.

Missing clients, skipped validation, schema-only proof, advisory results, generic
harness names, and English-only MCP product descriptions cannot pass.

Any failure blocks the affected artifact, client row, publication, documentation claim,
and release. It remains an unchecked plan step and is reported through the repository
issue tracker.

## Implementation

No product rename or translation change is authorized by this record.

The distribution-readiness plan adds verification at five boundaries:

1. Inventory the authored harness and every generated projection.
2. Inspect plugin, marketplace, MCPB, and client-display metadata in the frozen cohort.
3. Capture identifiers, the English MCP product description, and the Spanish MCP
   product description in every claimed installed Claude client.
4. Repeat the comparison after public marketplace and MCPB reacquisition.
5. Reconcile every observation in the close audit and leave failed deliverables open.

A distribution identity verifier reads one immutable release-cohort manifest. It owns
the inventory and JavaScript Object Notation (JSON) evidence schema. It fails for an
unprefixed harness identifier, a missing translation, a failed product-claim verdict,
or an artifact mismatch. Client evidence uses the same schema. A source assertion
cannot substitute for metadata observed in the client.

The implementation plan and its execution records define the commands and evidence.
`README.md`, `docs/workstation-setup.md`, and `docs/how-to/connect-an-agent.md` remain
the installation and connection guides. This explanation does not replace them.
Documentation can claim availability only after matching evidence passes.

If verification reports drift, a separate operator-approved implementation must define
the breaking migration. It must also approve the Spanish copy, generator changes,
routing changes, tests, and real-client proof. This decision cannot authorize that
work.

## Rationale

Full-boundary verification is the only option consistent with immutable tested-cohort
promotion. The product claim concerns identifiers and descriptions users receive, not
source intent or schema-valid construction.

This decision extends the one-authored-source and generated-output architecture without
changing it. It adds namespace parity and parity between the English and Spanish MCP
product descriptions to delivery evidence. The accepted Cadrumo identity tuple remains
unchanged.

## Consequences

The current authored harness fails the namespace invariant because its skills, personas,
and rules use unprefixed identifiers. Existing workspace and plugin tests preserve that
source-name equality. The current plugin, marketplace, and MCPB product descriptions
also fail bilingual parity. Top-level MCP server identity is already compliant, but
partial compliance cannot approve an artifact.

A later authorized migration has broad scope. It may change:

- skill metadata and directories
- persona settings
- agent filenames and frontmatter
- rule imports
- prompt names and resource URIs
- Claude workspace, plugin, marketplace, and MCPB metadata
- retained evidence, documentation, and tests

Existing client references may break.

Bilingual copy adds product review and real-client verification. Formats with one
description field may require combined text, which increases metadata size. These costs
are accepted because an unverified namespace or English-only MCP product surface is a
delivery defect rather than post-release polish.

This amendment extends the accepted distribution-readiness, Claude-packaging,
harness-refoundation, and active Cadrumo identity decisions. It does not edit or
reinterpret those accepted records in place.
