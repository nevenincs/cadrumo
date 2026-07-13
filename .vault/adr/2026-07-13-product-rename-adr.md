---
tags:
  - "#adr"
  - "#product-rename"
date: '2026-07-13'
related:
  - "[[2026-07-12-cadrumo-cli-executable-adr]]"
  - "[[2026-07-12-cadrumo-product-rename-research]]"
modified: '2026-07-13'
---
# `product-rename` adr: `product rename to Cadrumo across distributions, repository, and release surfaces` | (**status:** `accepted`)

## Problem Statement

The public product name is Cadrumo (working name selected and web-collision
screened by the public-product-name-clearance research; formally provisional
until trademark clearance), yet every published artefact still carries the
`aeat` stem: the PyPI distributions (`aeat-cli`, `aeat-data-manuals`,
`aeat-data-official`), the GitHub repository (`nevenincs/aeat`), the MCP
bundle id, the marketplace listing, the PyPI package description, and the
marketing copy. Operator directive: the `aeat-cli` package should no longer
exist; all PyPI and release packages, the repository, and associated
references assume the product rename. Beyond brand coherence this has a legal
edge: a PUBLISHED artefact named after the tax agency is a weaker
nominative-use posture than a product-named artefact that merely references
AEAT descriptively (frontend-legal-compliance and license-posture research).

## Considerations

- The `aeat` stem is load-bearing INTERNALLY at a different layer: the Python
  import package (`import aeat`), the module tree, the CLI verb tree
  (`aeat app ...` / `aeat config ...`), the JSON envelope `command=` contract
  identifiers, the MCP tool names (`aeat_*`), the error-registry suggestions,
  the four locale catalogues, and the agent-harness rules — roughly 3,700
  command citations across 600+ files, each guarded by conformance gates
  (documented-command, json-schema, rule-surface, suggestion-command).
- PyPI names cannot be renamed in place: a new project name is claimed by
  first upload (or pending Trusted Publisher registration); the old project
  is then deprecated/yanked, never deleted.
- GitHub repository renames preserve redirects for clones and links.
- The Spanish-stem rule keeps AEAT-surface DOMAIN vocabulary (`modelo`,
  `casilla`, `aeat.core` module names) untouched: the rename is a PRODUCT
  identity change, not a domain-vocabulary change.

## Considered options

- **Two-stage rename (chosen):** Stage A now — distribution names, repository,
  bundle/marketplace metadata, package description, marketing and legal
  references, install hints. Stage B as its own gated campaign — console
  scripts (`aeat`/`aeat-mcp` → `cadrumo`/`cadrumo-mcp`), the CLI root token in
  docs/locales/suggestions/harness, envelope `command=` identifiers, MCP tool
  prefix. Keeps every conformance gate green at each step.
- **Big-bang rename including the command surface:** rejected for this pass —
  the 3,700-citation sweep across contract identifiers and four locale
  catalogues cannot be verified within one change without red gates; the
  aeat-cli-pull-and-file-standard rule documents exactly how partial verb
  renames strand operators.
- **Rename distributions only, keep `aeat` branding elsewhere:** rejected —
  leaves repository and marketing incoherent with the shipped name.

## Constraints

- `Cadrumo` remains legally provisional until formal mark clearance (classes
  9/42 first); the rename does not create prior-restraint risk because the
  name was collision-screened, but clearance stays a live follow-up.
- The PyPI names `cadrumo`, `cadrumo-data-manuals`, `cadrumo-data-official`
  must be registered as pending Trusted Publishers (or first-uploaded) by the
  operator before the publish workflow can ship them.
- The Python import package stays `aeat` in Stage A AND Stage B unless a
  future ADR decides otherwise: it is internal API, not a published product
  name, and renaming it rewrites every import in the tree for no user-facing
  gain.

## Implementation

Stage A (this change): root distribution renamed `aeat-cli` → `cadrumo` with a
Cadrumo-branded description and keywords; companions renamed
`aeat-data-manuals`/`aeat-data-official` → `cadrumo-data-manuals`/
`cadrumo-data-official` (directories and the `aeat_data` namespace package
unchanged — distribution name and import name are independent); the
`corpus-sources` pins, install hints (`pip install cadrumo[<extra>]`), publish
workflow choices and guards, packaging gates, smoke lanes, release tooling,
README/marketing/legal references, and the frontend PyPI links all follow; the
GitHub repository renames `nevenincs/aeat` → `nevenincs/cadrumo` with
redirects, and every in-repo URL follows. Historical `.vault/` records keep
their original names (they record what was true). Stage B (follow-up
campaign): console scripts, CLI root token, envelope command identifiers, MCP
tool prefix, harness citations, locale sweeps — executed under the
aeat-cli-pull-and-file-standard sweep discipline with all conformance gates.

## Rationale

The clearance research selected Cadrumo and the operator mandated the rename;
staging by surface keeps every gate green while removing the agency's name
from every PUBLISHED artefact identity immediately — the surface where
nominative-use posture matters most. The internal/domain uses of `aeat` are
descriptive and gate-protected, and their rename is mechanical but
verification-heavy, so it rides its own campaign.

## Consequences

- The old PyPI projects (`aeat-cli` 0.1.x, `aeat-data-*` ≤0.2.0) remain
  published; the operator should deprecate them after the first `cadrumo`
  release (yank superseded releases; the project pages stay as tombstones
  pointing at `cadrumo`).
- Until Stage B, `pip install cadrumo` still installs console scripts named
  `aeat` and `aeat-mcp` — documented in the README so the seam is explicit,
  and removed by the Stage B campaign.
- The marketplace plugin id (`aeat@neve`) and the external
  `nevenincs/neve-marketplace` listing are operator-owned follow-ups.
- All version history and provenance is preserved; the repository rename
  redirects old clones and links.

## Status note: accepted Stage-A decision with binding overrides (2026-07-13)

This ADR remains accepted only for its Stage-A distribution, repository,
install, publication, marketplace, marketing, and legal scope. That accepted
role records and continues to authorize the public release-surface rename; it
does not make this document a parallel authority for product casing,
executables, imports, or machine identifiers.

The accepted `2026-07-12-cadrumo-cli-executable-adr` is the single binding
naming authority for the product display, Python import root, human CLI
executable, and related machine identities. Accordingly, this ADR's Stage-B
console-script proposal and `aeat` import-package constraint are struck and
are not active requirements. Remaining Stage-B work follows the binding CLI
ADR's identity boundary, including `Cadrumo` in sentence prose, `CADRUMO` in
identity contexts, human executable `aeat`, MCP executable `cadrumo-mcp`, and
Python import root `cadrumo`.
