---
tags:
  - '#research'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:c219c64062454330fd66822d45763222d3cd48666863266f478e43101f613529'
related: []
---

# `cadrumo-product-rename` research: `Cadrumo product rename`

This research maps the code, packaging, integration, persistence, test, locale,
and documentation surfaces affected by renaming the unreleased product to
Cadrumo. Semantic discovery located the implementation and decision clusters;
targeted exact-name searches then confirmed concrete identity-bearing sites.

## Findings

### Product and authority identities are different concepts

The current spelling `AEAT` is overloaded. It identifies both the product and
the Agencia Estatal de Administracion Tributaria. Product-owned identities must
be renamed to Cadrumo, while authority names, official URLs, legal provenance,
wire terminology, and authority taxonomies must retain AEAT. In particular,
`src/aeat/adapters/outbound/aeat`, `src/aeat/_data/registry/aeat`, official corpus
source identifiers, and AEAT-assigned filing fields describe the external
authority rather than the product.

Mixed sentences require referent-aware editing. For example, operator copy may
continue to say that no AEAT session is active while changing the command it
recommends from `aeat` to `cadrumo`. A repository-wide textual replacement would
corrupt legal meaning and bundled evidence.

### Recommended canonical product identity

The pre-release no-legacy regime supports a hard cut with no aliases or shims.
The recommended canonical tuple is display name `Cadrumo`, Python import and
human CLI `cadrumo`, MCP executable `cadrumo-mcp`, MCP/plugin/server identity
`cadrumo`, and product environment prefix `CADRUMO_`. The distribution name,
companion corpus distributions, shared companion namespace, repository identity,
and marketplace identity must be settled explicitly in the ADR rather than
derived mechanically from the old tuple.

No `aeat` import shim, old console alias, dual environment-variable parser, or
automatic old-state migration should be introduced. Product-owned persistence
roots and namespaces should move at one explicit breaking boundary. External
authority configuration such as an AEAT endpoint or credential concept may keep
the AEAT name because it configures the counterparty, not the application.

### Runtime blast radius

`pyproject.toml` binds the present distribution, `aeat` and `aeat-mcp` console
scripts, extras, and `src/aeat` wheel selection. The package move must update
absolute imports, `importlib.resources.files("aeat")`, dynamic import strings,
registry callable targets embedded in TOML, error registries, import-smoke tests,
and generated API references as one coherent wave.

The MCP surface carries product identity in tool prefixes, client prefixes,
resource URI schemes, server names, subprocess argv, plugin metadata, allowlists,
snapshots, and generated `.mcp.json`. Tool-name budgets must be recomputed after
the prefix changes. The generator in `src/aeat/agent/_workspace.py` is the
authority for generated marketplace artifacts and must change before regeneration.

Product persistence identity is embedded in the application directory, database
filename, authentication-session root, logical storage namespaces, and bundle
extension. These names are durable format boundaries and cannot be changed in
independent partial commits. The hard-cut policy should refuse incompatible state
clearly rather than silently reading the old namespace.

### Packaging and release blast radius

The root distribution is coupled to two independently published corpus-source
distributions under `packaging/aeat_data_manuals` and
`packaging/aeat_data_official`, with a shared `aeat_data` PEP 420 namespace.
Their project metadata, build hooks, source mappings, root dependency sources,
smoke tests, and publication workflow form one packaging seam. `uv.lock` is a
generated result and should be regenerated only after all project metadata moves.

The Claude plugin marketplace is primary and MCPB is a demoted secondary
artifact under the accepted Claude ecosystem packaging decision. The plugin
generator, marketplace manifest, MCPB manifest/build/test, release workflows,
`justfile`, packaging smoke tools, and release documentation all embed exact
product names. PyPI Trusted Publisher registrations are external exact-name state;
new project registrations must exist before publication can succeed.

As of 2026-07-12, direct checks returned no existing exact PyPI project or GitHub
account for `cadrumo`. This is only an availability signal, not reservation or
trademark clearance. The root and companion project names, repository/organization,
plugin identifiers, PATH executable, domains, and Spanish/EU trademarks require
reservation or clearance before a public launch claim.

### Documentation, locale, and generated-content policy

Active user documentation must present Cadrumo as the product while preserving
AEAT as the authority. Historical ADR, research, audit, plan, and execution prose
records prior identity and should not be bulk-rewritten; a new ADR should supersede
only decisions whose active product naming is replaced. Bundled official evidence,
source URLs, hashes, and legal data are immutable rename exclusions.

Locales must be changed through the locale CLI, with command-help sources sequenced
before documentation verification. API stubs must be regenerated through the
documentation scaffold tool rather than edited manually. Generated build output is
not an authoring target. Substantive user-document rewrites remain subject to the
repository's staged documentation workflow and approval gates.

### Recommended implementation order

1. Approve an identity matrix separating product, authority, and historical uses,
   including the hard-cut compatibility and persistence policy.
2. Reserve external distribution, repository, marketplace, and trademark names.
3. Establish one product-identity authority, then atomically move the root package,
   dynamic import targets, and both companion distributions/namespaces.
4. Update distribution metadata, scripts, extras, build hooks, and regenerate the
   lockfile and wheels.
5. Change product configuration, persistence, CLI, MCP, plugin, and generated
   integration identities without transitional aliases.
6. Update tests, developer tooling, CI/release automation, locales, and active docs;
   regenerate all derived artifacts.
7. Run import, packaging, persistence, MCP handshake, locale, documentation,
   feature-surface, and full residue gates. Residue checks must allow legitimate
   authority uses of AEAT rather than require zero occurrences globally.

### Workspace constraint

Discovery found the checkout on `chore/eliminate-shims` with hundreds of modified,
deleted, and untracked paths owned by concurrent work. Rename execution must use
explicit path ownership checks before every edit and must not begin until the ADR
and plan are approved. A blind bulk mutation in the current shared state would be
unsafe.
