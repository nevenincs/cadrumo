---
tags:
  - "#adr"
  - "#cadrumo-cli-executable"
date: '2026-07-12'
related:
  - "[[2026-07-12-cadrumo-product-rename-research]]"
supersedes:
  - '2026-07-12-cadrumo-product-rename-adr'
modified: '2026-07-12'
---
# `cadrumo-cli-executable` adr: `Cadrumo product identity with AEAT CLI executable` | (**status:** `accepted`)

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
artifacts, release naming, state boundary, and authority-owned terminology. Its
recommended human CLI spelling is the sole element overridden by this decision.

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

The canonical identity tuple is: display name `Cadrumo`; Python package and
root distribution `cadrumo`; human command-line executable `aeat`; MCP
executable `cadrumo-mcp`; product environment prefix `CADRUMO_`; and companion
namespace `cadrumo_data`. The human executable is a deliberate, singular
operator contract, not a legacy alias.

The installed `aeat` entry point must resolve directly to the Cadrumo CLI
callable. `import cadrumo` is the supported Python import; `import aeat` must
not be restored or documented as supported. Product state and configuration
continue to make one hard Cadrumo cut, with no dual reader or automatic old
state migration.

Authority-owned `AEAT` names remain correct for official endpoints,
credentials, legal provenance, registry classifications, evidence, and
statements about the counterparty. The previously accepted packaging,
resource-boundary, compatibility-lifecycle, persistence, and safety decisions
remain stable constraints. This ADR only changes the human executable element
of the renamed product tuple and supersedes the prior rename ADR as its active
source of naming authority.


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
gates gain an unambiguous three-part proof: Cadrumo import succeeds, `aeat`
executes it, and no `aeat` import compatibility surface exists.

The exception means zero-occurrence brand checks are invalid: `aeat` remains
required when it denotes the sole executable or the authority. Reviews must
classify those uses by contract and referent rather than mechanically rename
them. A future request to add `cadrumo` as another executable requires a new
decision because it would change the single-command guarantee.
