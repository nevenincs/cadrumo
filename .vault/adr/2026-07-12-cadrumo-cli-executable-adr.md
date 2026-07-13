---
tags:
  - "#adr"
  - "#cadrumo-cli-executable"
date: '2026-07-12'
related:
  - "[[2026-07-12-cadrumo-product-rename-research]]"
supersedes:
  - '2026-07-12-cadrumo-product-rename-adr'
modified: '2026-07-13'
---
# `cadrumo-cli-executable` adr: `Cadrumo product identity with aeat CLI executable` | (**status:** `accepted`)

## Problem Statement

The accepted Cadrumo rename establishes the correct product/authority boundary,
but its required human executable `cadrumo` conflicts with the approved current
operator contract: the command-line executable remains `aeat`. Treating
`aeat` as an old alias would create a false compatibility narrative; retaining
an `aeat` Python package would create the prohibited dual runtime identity.

This ADR replaces the conflicting rename decision while preserving its
referent-aware treatment of the AEAT authority and its hard-cut policy for
Python imports, configuration, persistence, and integrations.

## Considerations

`Cadrumo` is the product name. AEAT remains the Spanish tax authority, its
official protocol and evidence vocabulary, and the institution the product
interacts with. These referents must stay distinct in active prose and runtime
contracts.

An executable name and a Python import root are independent interfaces. The
approved executable is exactly `aeat`; the approved Python root is exactly
`cadrumo`. The command must invoke the Cadrumo implementation directly. No
second executable name, import fallback, wrapper package, or compatibility
claim is permitted.

The parent rename research remains applicable to the package move, generated
artifacts, release naming, state boundary, and authority-owned terminology. This
decision overrides two elements of the parent tuple: the product display casing
is exactly `Cadrumo`, and the sole human CLI executable is exactly `aeat`.

## Considered options

- **Choose: Cadrumo product and import root with one canonical `aeat` CLI.**
  This keeps the approved operator command stable while giving the product one
  direct runtime implementation.
- **Reject: make `cadrumo` the human executable.** It contradicts the current
  approved command contract.
- **Reject: keep both `aeat` and `cadrumo` executables.** Dual names make one
  a compatibility alias and reintroduce the split identity this rename removes.
- **Reject: provide an `aeat` Python package shim.** It creates a second import
  root and misleadingly conflates a command name with package compatibility.
- **Reject: revert the product identity to AEAT.** It erases the required
  distinction between Cadrumo as product and AEAT as authority.

## Constraints

The complete canonical identity matrix is:

- product display name: `Cadrumo` (title case in prose; see Casing and styling);
- Python package, root distribution, and repository identifier: `cadrumo`;
- sole human command-line executable: `aeat`;
- MCP server identifier, tool prefix, and resource URI scheme: `cadrumo`;
- plugin identifier: `cadrumo`;
- MCP executable: `cadrumo-mcp`;
- product environment prefix: `CADRUMO_`;
- companion distributions: `cadrumo-data-manuals` and
  `cadrumo-data-official`;
- companion namespace: `cadrumo_data`; and
- Spanish tax authority short name: `AEAT`.

The human executable is a deliberate, singular operator contract, not a legacy
alias. Lowercase `cadrumo` remains correct for the listed machine identities; it
is not the human executable or the product display casing.

The installed `aeat` entry point must resolve directly to the Cadrumo CLI
callable. `import cadrumo` is the supported Python import; `import aeat` must
not be restored or documented as supported. Product state and configuration
continue to make one hard Cadrumo cut, with no dual reader or automatic old
state migration.

Authority-owned `AEAT` names remain correct for official endpoints,
credentials, legal provenance, registry classifications, evidence, and
statements about the counterparty. The previously accepted packaging,
resource-boundary, compatibility-lifecycle, persistence, and safety decisions
remain stable constraints. This ADR changes the human executable and product
display casing elements of the renamed product tuple, and
supersedes the prior rename ADR as its active source of naming authority.

> **Operator re-confirmation (2026-07-13).** During execution an agent re-flipped the
> console script to `cadrumo` (commit `ecadfe08ba`, "restore canonical Cadrumo
> executable"). The operator adjudicated explicitly: the product name Cadrumo is
> binding for all user documentation, and the binary CLI command retains `aeat` —
> this ADR remains binding. Do not rename the console script to `cadrumo`.

## Implementation

Keep exactly one human CLI console-script declaration named `aeat`, pointed
directly at the Cadrumo CLI entry callable, and retain the distinct MCP
console-script declaration named `cadrumo-mcp`, pointed at the Cadrumo MCP
entry callable. Keep all Cadrumo application code and Python imports under the
`cadrumo` root; remove or correct stale checks that demand an `aeat` import
package instead of adding a shim.

Project the same distinction into command help, user documentation, packaging
proofs, developer tooling, and release checks: product prose says Cadrumo;
operator invocations use `aeat`; authority interactions retain AEAT. Verify
the installed artifact, not only source-tree imports: `aeat --help` must run
the Cadrumo CLI, `import cadrumo` must succeed, and `import aeat` must not be a
supported compatibility path.

> **Operator re-confirmation, second (2026-07-13).** A concurrent fleet (plan steps
> W01.P02.S89-S90) re-committed all-caps `CADRUMO` as the binding prose display and
> removed the casing section below. The operator adjudicated again: running prose
> uses `Cadrumo`; all-caps `CADRUMO` is the wordmark/logotype treatment only. The
> section below is the binding casing contract; do not re-apply all-caps to prose,
> the identity tuple, or locale catalogue strings.

## Casing and styling (mandated)

Every surface uses exactly one of these treatments; any other spelling of the
product or command names is a defect:

- **Cadrumo** — the product display name in running prose: user documentation,
  README, release notes, locale catalogue prose, CLI help sentences, docstring
  prose, and commit/PR prose. Never lowercase in prose, never all-caps in
  prose, and never code-styled when naming the product rather than the
  package.
- **CADRUMO** (all-caps) — the wordmark/logotype treatment ONLY, taken from the
  Figma/marketing brand: the site header brand lockup and equivalent logotype
  renderings (e.g. the documentation site header wordmark). It is a typographic
  treatment of the display name, not an alternative spelling; it never appears
  in running prose.
- **`cadrumo`** (lowercase, code-styled) — the Python import root, the PyPI
  distribution, the plugin identifier, and the MCP server/tool prefix/resource
  scheme. Always rendered as code (backticks in Markdown, ``code`` in RST).
- **`aeat`** (lowercase, code-styled) — the human CLI executable, only ever as
  the command token in invocations (`aeat config ...`, `aeat app ...`,
  `aeat --help`). Prose never uses "aeat" as a product or brand name.
- **`cadrumo-mcp`** (lowercase, code-styled) — the MCP executable.
- **`CADRUMO_*`** (upper snake, code-styled) — product-owned environment
  variables. Authority-owned portal/credential variables keep their `AEAT_*`
  names.
- **`cadrumo-data-manuals`** / **`cadrumo-data-official`** /
  **`cadrumo_data`** (lowercase, code-styled) — companion distributions and
  their shared namespace package.
- **AEAT** (all-caps, plain prose) — the Spanish tax authority acronym, its
  portals, protocols, credentials, and legal provenance. Never code-styled when
  naming the institution; `aeat` code style is reserved for the executable and
  for authority-scoped path segments (`adapters/outbound/aeat`,
  `_data/registry/aeat`).

The runtime projection of the prose display name is
``PRODUCT_IDENTITY.display_name == "Cadrumo"``; the all-caps wordmark is a
presentation-layer treatment and MUST NOT be encoded into the identity tuple,
locale catalogue prose, or any persisted value.

## Rationale

The rename research establishes that product and authority spellings cannot be
globally replaced and that dual runtime identities would be unsafe. The current
approved command contract supplies the missing distinction: executable naming
is an operator interface, not evidence that the Python root or product brand is
AEAT.

One direct `aeat`-to-Cadrumo binding honors both facts. It removes the broken
partial-rename ambiguity without presenting `aeat` as a deprecated alias, and
it preserves the no-shim rule where duplication would harm architecture rather
than help operators.

## Consequences

Active product material can consistently call the product Cadrumo while giving
operators one truthful command to run. Import, packaging, and documentation
gates gain an unambiguous three-part proof: `cadrumo` import succeeds, `aeat`
executes it, and no `aeat` import compatibility surface exists.

The exception means zero-occurrence brand checks are invalid: `aeat` remains
required when it denotes the sole executable or the authority. Reviews must
classify those uses by contract and referent rather than mechanically rename
them. A future request to add `cadrumo` as another executable requires a new
decision because it would change the single-command guarantee.
