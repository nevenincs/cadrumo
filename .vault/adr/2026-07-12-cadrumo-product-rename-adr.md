---
tags:
  - "#adr"
  - "#cadrumo-product-rename"
date: '2026-07-12'
related:
  - "[[2026-07-12-cadrumo-product-rename-research]]"
superseded_by: '2026-07-12-cadrumo-cli-executable-adr'
modified: '2026-07-17'
body_hash: 'sha256:961099e75f9dfdbba255579cb2ee99c1d4e5b628c84cc513bf7c952ea5443f7c'
---

# `cadrumo-product-rename` adr: `Canonical Cadrumo product identity and rename boundary` | (**status:** `superseded`)

## Problem Statement

The unreleased product currently uses `aeat` as its package, command,
distribution, MCP, plugin, configuration, persistence, repository, and
documentation identity. That spelling also correctly names the external Spanish
tax authority. A mechanical replacement would corrupt authority adapters,
official URLs, legal provenance, registry taxonomy, filing terminology, and
historical evidence, while an incomplete rename would leave a split identity.

This ADR establishes one canonical Cadrumo identity, a referent-based boundary
between product and authority uses, and the breaking-change policy for imports,
commands, configuration, persisted state, packaging, generated artifacts,
historical records, and externally reserved names.

## Considerations

The project is pre-release and governed by the no-legacy-compatibility rule.
Existing decisions require a single authoritative runtime/package path,
installed-artifact proofs, reviewed bundled legal data, generator-owned derived
artifacts, and the Claude marketplace as the primary agent distribution.

`AEAT` remains the legal name of the counterparty. Authority-owned concepts
include the outbound AEAT adapter, official endpoints and credentials,
authority-assigned fields, the `registry/aeat` taxonomy, official corpus
identifiers, citations, hashes, and statements about interaction with AEAT.
Product-owned concepts include the Python root, executable and distribution
names, plugin and MCP namespaces, application configuration and state,
repository identity, documentation branding, and generated product metadata.

The rename crosses imports and resource lookup, dynamic callable strings,
entry points, MCP wire names, companion distributions, environment variables,
platform state, storage namespaces, tests, locales, CI/release tooling, API
references, marketplace output, lockfiles, and publication registrations.
These surfaces must converge at one breaking boundary. Availability checks are
signals only; they reserve no project, account, identifier, domain, or mark.

## Considered options

- **Choose: one referent-aware hard cut to Cadrumo.** This produces one coherent
  identity, preserves AEAT as the authority, and avoids permanent compatibility
  machinery; it requires coordinated implementation and explicit state refusal.
- **Reject: global textual replacement.** It would alter official and legal
  meaning, bundled evidence, URLs, and historical records.
- **Reject: gradual dual identity.** Shims, aliases, dual environment parsing,
  namespace fallbacks, and migration contradict the no-legacy regime.
- **Reject: presentation-only rebrand.** Retaining `aeat` runtime identities
  would leave packages, integrations, diagnostics, and operators split.
- **Reject: retain old persistence names.** Application roots, databases,
  namespaces, and bundle suffixes are observable durable contracts.

## Constraints

The canonical tuple is display name `Cadrumo`; Python package, root
distribution, human CLI, repository, MCP server, tool prefix, resource URI
scheme, and plugin identifier `cadrumo`; MCP executable `cadrumo-mcp`;
product environment prefix `CADRUMO_`; companion distributions
`cadrumo-data-manuals` and `cadrumo-data-official`; and companion namespace
`cadrumo_data`. An independently named publisher marketplace may keep its
publisher identity, but its product entry and source path become `cadrumo`.

AEAT names remain when they denote the authority, portals, protocols,
credentials, official artifacts, legal provenance, or registry classification.
Mixed settings and prose are classified by referent. Product controls move to
`CADRUMO_*`; authority endpoint and authentication concepts may retain
`AEAT_*`. The plan must classify every ambiguous public setting.

There will be no `aeat` import shim, old console alias, dual environment
reader, MCP or plugin alias, namespace fallback, or automatic old-state
migration. Old product state is incompatible and is never silently opened as
Cadrumo state. Product persistence changes as one cut. Cadrumo starts with new
state or clearly refuses detected old state. Any export/import facility needs
a separate approved decision.

Historical vault records are not bulk-rewritten. This ADR replaces active
naming intent only where it conflicts. Official evidence, URLs, citations,
hashes, and legal corpus content are never rebranded. Generated files are not
hand-edited; their authorities change first and derivatives are regenerated.

Public release is blocked until the root and companion package names,
repository/organization and marketplace identifiers, executable expectations,
relevant domains, and Spanish/EU trademark position are reserved or cleared.
A passing availability query does not satisfy this gate.

Accepted packaging, resource-boundary, Claude ecosystem,
secure-persistence and profile-state decisions remain
stable parent constraints. This ADR changes product spelling and cutover
identity, not architecture, safety policy, or authority semantics.

## Implementation

Introduce one authoritative product-identity definition consumed by packaging,
runtime, CLI, MCP, plugin generation, persistence naming, diagnostics, and
release tooling. Move the Python and companion trees atomically, then update
static imports, resource lookups, dynamic strings, registry targets, error
registries, build mappings, extras, and installed-artifact probes before
removing old roots.

Project the identity into console scripts and MCP/plugin wire surfaces,
including executable, server, tool prefix, resource scheme, subprocess argv,
manifests, marketplace entry, allowlists, name budgets, and generated config.
Apply persistence as a coordinated boundary: Cadrumo writes only Cadrumo roots,
filenames, namespaces, and bundles. Boundaries may detect old state and refuse;
they do not read, move, re-key, or delete it.

Classify settings, modules, locale strings, and documentation by referent.
Rename product uses and retain authority uses through mandated locale and
documentation workflows. Change generators before regenerating lockfiles,
wheels, plugin output, MCPB, API references, indexes, and snapshots. Verify
positive Cadrumo behavior plus scoped residue gates that allow documented AEAT
authority uses. Publish nothing until external reservation is evidenced.

## Rationale

Research shows that `aeat` currently represents two entities. A referent-aware
hard cut is the only option that creates a truthful product identity without
damaging the authority model or institutionalizing legacy paths. Pre-release
status makes this the lowest-risk point to break product names and abandon old
local state.

One tuple prevents drift between packaging, imports, commands, MCP clients,
plugins, configuration, persistence, and release automation. Keeping AEAT for
the authority clarifies the architecture: Cadrumo is the application; AEAT is
an external institution it models and interacts with under existing gates.

Central identity authority, generator-first updates, installed-artifact proof,
and an external reservation gate address missed dynamic strings, stale output,
partially renamed state, broken publisher registrations, and unsupported naming
claims.

## Consequences

Cadrumo gains a coherent identity across source, runtime, integrations,
artifacts, state, and documentation. Residue checks can distinguish obsolete
branding from correct authority terminology, and contributors gain a durable
naming boundary.

The change is intentionally breaking. Existing imports, commands, product
environment variables, MCP/plugin identifiers, package pins, and application
state stop working. Operators and developers must reinstall, update integrations
and configuration, and create fresh state. Avoiding a compatibility window
reduces long-term complexity but increases cutover coordination.

The implementation cannot be a blind replacement. Dynamic references,
companion packaging, serialized namespaces, generated indexes, multilingual
copy, and release automation require ordered verification. Historical records
retain the former name, so global zero-occurrence checks are invalid.

External naming and trademark clearance can delay publication after code
completion. Until reservation evidence exists, builds may be tested locally but
are not publicly secured or release-ready. The product/authority distinction
becomes permanent: new `AEAT` names identify the authority, while product
identity comes from the canonical Cadrumo authority.
