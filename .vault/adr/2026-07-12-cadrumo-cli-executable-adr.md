---
tags:
  - "#adr"
  - "#cadrumo-cli-executable"
date: '2026-07-12'
related:
  - "[[2026-07-12-cadrumo-product-rename-research]]"
supersedes:
  - '2026-07-12-cadrumo-product-rename-adr'
modified: '2026-07-17'
body_hash: 'sha256:c56a4e6f41b1524e1076dadb462ec5ef2d0f9e56a43df2ab5b0a8750edd9d90b'
---
# `cadrumo-cli-executable` adr: `CADRUMO product identity with aeat CLI executable` | (**status:** `accepted`)

## Problem Statement

The accepted CADRUMO rename establishes the correct product/authority boundary,
but its required human executable `cadrumo` conflicts with the approved current
operator contract: the command-line executable remains `aeat`. Treating
`aeat` as an old alias would create a false compatibility narrative; retaining
an `aeat` Python package would create the prohibited dual runtime identity.

This ADR replaces the conflicting rename decision while preserving its
referent-aware treatment of the AEAT authority and its hard-cut policy for
Python imports, configuration, persistence, and integrations.

## Considerations

`CADRUMO` is the product name. AEAT remains the Spanish tax authority, its
official protocol and evidence vocabulary, and the institution the product
interacts with. These referents must stay distinct in active prose and runtime
contracts.

An executable name and a Python import root are independent interfaces. The
approved executable is exactly `aeat`; the approved Python root is exactly
`cadrumo`. The command must invoke the CADRUMO implementation directly. No
second executable name, import fallback, wrapper package, or compatibility
claim is permitted.

The parent rename research remains applicable to the package move, generated
artifacts, release naming, state boundary, and authority-owned terminology. This
decision overrides two elements of the parent tuple: the product display casing
is exactly `CADRUMO`, and the sole human CLI executable is exactly `aeat`.

## Considered options

- **Choose: CADRUMO product and import root with one canonical `aeat` CLI.**
  This keeps the approved operator command stable while giving the product one
  direct runtime implementation.
- **Reject: make `cadrumo` the human executable.** It contradicts the current
  approved command contract.
- **Reject: keep both `aeat` and `cadrumo` executables.** Dual names make one
  a compatibility alias and reintroduce the split identity this rename removes.
- **Reject: provide an `aeat` Python package shim.** It creates a second import
  root and misleadingly conflates a command name with package compatibility.
- **Reject: revert the product identity to AEAT.** It erases the required
  distinction between CADRUMO as product and AEAT as authority.

## Constraints

The complete canonical identity matrix is:

- product display name: `CADRUMO`;
- Python package and root distribution: `cadrumo`;
- owner-qualified repository slug: `nevenincs/cadrumo`;
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

The installed `aeat` entry point must resolve directly to the CADRUMO CLI
callable. `import cadrumo` is the supported Python import; `import aeat` must
not be restored or documented as supported. Product state and configuration
continue to make one hard CADRUMO cut, with no dual reader or automatic old
state migration.

Authority-owned `AEAT` names remain correct for official endpoints,
credentials, legal provenance, registry classifications, evidence, and
statements about the counterparty. Packaging, resource-boundary, persistence,
and safety decisions remain stable constraints. This ADR changes the human executable and product
display casing elements of the renamed product tuple, and
supersedes the prior rename ADR as its active source of naming authority.

> **Operator re-confirmation (2026-07-13).** During execution an agent re-flipped the
> console script to `cadrumo` (commit `ecadfe08ba`, "restore canonical Cadrumo
> executable"). The operator adjudicated explicitly: the product name CADRUMO is
> binding for all user documentation, and the binary CLI command retains `aeat` —
> this ADR remains binding. Do not rename the console script to `cadrumo`.

## Implementation

Keep exactly one human CLI console-script declaration named `aeat`, pointed
directly at the CADRUMO CLI entry callable, and retain the distinct MCP
console-script declaration named `cadrumo-mcp`, pointed at the CADRUMO MCP
entry callable. Keep all CADRUMO application code and Python imports under the
`cadrumo` root; remove or correct stale checks that demand an `aeat` import
package instead of adding a shim.

Project the same distinction into command help, user documentation, packaging
proofs, developer tooling, and release checks: product prose says CADRUMO;
operator invocations use `aeat`; authority interactions retain AEAT. Verify
the installed artifact, not only source-tree imports: `aeat --help` must run
the CADRUMO CLI, `import cadrumo` must succeed, and `import aeat` must not be a
supported compatibility path.

## Rationale

The rename research establishes that product and authority spellings cannot be
globally replaced and that dual runtime identities would be unsafe. The current
approved command contract supplies the missing distinction: executable naming
is an operator interface, not evidence that the Python root or product brand is
AEAT.

One direct `aeat`-to-CADRUMO binding honors both facts. It removes the broken
partial-rename ambiguity without presenting `aeat` as a deprecated alias, and
it preserves the no-shim rule where duplication would harm architecture rather
than help operators.

## Consequences

Active product material can consistently call the product CADRUMO while giving
operators one truthful command to run. Import, packaging, and documentation
gates gain an unambiguous three-part proof: `cadrumo` import succeeds, `aeat`
executes it, and no `aeat` import compatibility surface exists.

The exception means zero-occurrence brand checks are invalid: `aeat` remains
required when it denotes the sole executable or the authority. Reviews must
classify those uses by contract and referent rather than mechanically rename
them. A future request to add `cadrumo` as another executable requires a new
decision because it would change the single-command guarantee.

## Status note: the single binding naming ADR

Operator decision recorded 2026-07-13, during the 476-to-main reconciliation:
the `aeat` executable STAYS, and this ADR is the ONE binding naming authority
for the product/executable/import identity. The decision resolves the
inter-ADR conflict as follows:

- `2026-07-12-cadrumo-product-rename-adr` is formally superseded by this ADR
  (its `cadrumo` executable requirement was the conflicting element this ADR
  always replaced; the supersession is now recorded in frontmatter).
- `2026-07-13-product-rename-adr` remains accepted for its Stage-A scope only
  (distribution names, repository `nevenincs/cadrumo`, marketplace and
  marketing surfaces). Its Stage-B console-script rename
  (`aeat`/`aeat-mcp` to `cadrumo`/`cadrumo-mcp`) is STRUCK by this decision:
  the sole human executable is exactly `aeat`, permanently, unless a future
  ADR supersedes this one. The remaining Stage-B items that do not touch the
  executable (MCP tool prefix, envelope identifiers, locale citations) follow
  the identity boundary this ADR defines.
- Display casing: active prose follows the shipped corpus and the Stage-A
  ADR - `Cadrumo` in sentence prose, `CADRUMO` acceptable in identity
  contexts; the "exactly CADRUMO" casing sentence in this ADR's
  Considerations is relaxed to that corpus convention by this note.

The binding naming tuple, in one place: product `Cadrumo` (prose) /
`CADRUMO` (identity contexts); sole human executable `aeat`; MCP server
script `cadrumo-mcp`; Python import root `cadrumo`; PyPI distributions
`cadrumo`, `cadrumo-data-manuals`, `cadrumo-data-official`; repository
`nevenincs/cadrumo`; product env-var prefix `CADRUMO_*`; authority-owned
vocabulary (`AEAT_CERTIFICATE_*`, `AEAT_BROWSER_*`, modelo/casilla domain
terms) stays `AEAT`/Spanish per the Spanish-stem rule.
