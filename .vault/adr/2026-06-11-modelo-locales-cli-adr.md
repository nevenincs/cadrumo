---
tags:
  - '#adr'
  - '#modelo-locales-cli'
date: '2026-06-11'
related:
  - '[[2026-06-11-modelo-locales-cli-research]]'
---

# `modelo-locales-cli` adr: `aeat.locales manages modelo schema-local translations` | (**status:** `accepted`)

## Problem Statement

Modelo schema localization is currently implemented at runtime through registry-local TOML files, but authoring those files directly bypasses the command discipline used for core application translation keys. That creates a governance split: `tr(...)` catalogue work is managed through `python -m aeat.locales`, while modelo casilla labels and help strings can be edited by hand. This ADR decides that the same locale CLI surface must become the write authority for modelo schema-local translations.

## Considerations

- Core application locale catalogues and modelo schema-local catalogues have different storage and loading constraints. Core `tr(...)` strings live in eager YAML files, while schema-local casilla labels/help live in lazy registry TOML files.
- The `2026-06-08-registry-localization-backend-adr` keeps official Spanish casilla `label` values in registry schema TOML as legally bound invariants. The CLI must never replace those invariant labels with operator-language text.
- Modelo schema translation scale is large. Some revisions contain thousands of casillas, so the CLI must support per-modelo and per-revision work rather than assuming a single global catalogue operation is practical.
- Existing registry loader validation already rejects locale keys that do not match real `casilla_id` or `continuidad_id`. The authoring CLI should run equivalent checks before writes and use the loader audit as a final verification path.
- Existing project rules require locale catalogue work to go through `aeat.locales`. Extending that module preserves one command family for localization instead of introducing a parallel registry-specific localization tool.

## Constraints

- The CLI must preserve lazy loading. Modelo translations remain in registry-local TOML under modelo or revision `locales/` directories; they are not scaffolded into the eager `src/aeat/locales/*.yml` catalogues.
- The CLI must preserve legal Spanish invariants. It may write localized `labels` and `help` maps, but it must not mutate `CasillaDefinition.label`, official schema identifiers, export layout strings, or AEAT record-design constants.
- The CLI must be rigorous enough for concurrent campaigns. It needs deterministic output, path containment checks, key validation, and per-modelo coverage reporting so parallel agents can coordinate without broad worktree rewrites.
- The CLI must not hide drift. `scaffold --check`-style gates for modelo schema localization must fail when required locale TOML files are missing keys or contain stale keys.
- The architecture depends on the registry-localization backend staying stable: `localized_labels`, `localized_help`, loader injection, locale TOML fingerprinting, and referential-integrity validation are the runtime contract the CLI manages.

## Implementation

Extend `aeat.locales` with a modelo-schema sub-surface rather than adding a new root command. The surface should keep the existing top-level verbs for core YAML catalogues and add explicit modelo-local verbs whose names make the registry target clear.

The command contract should include:

- `python -m aeat.locales modelo audit` to report schema-local translation coverage and drift by modelo, revision, locale, field kind, and key.
- `python -m aeat.locales modelo scaffold` to create or align registry-local TOML files for selected modelos/revisions/locales without overwriting existing translated leaves.
- `python -m aeat.locales modelo scaffold --check` to fail on missing locale files, missing label/help keys, stale keys, malformed TOML, or invalid references.
- `python -m aeat.locales modelo set LOCALE MODELO REVISION FIELD KEY VALUE` to set one translated `labels` or `help` leaf after validating the modelo/revision/key against the registry.
- `python -m aeat.locales modelo remove LOCALE MODELO REVISION FIELD KEY` to remove one schema-local translation leaf with the same containment and referential checks.
- `python -m aeat.locales modelo coverage` to emit per-modelo/revision completion counts for campaign tracking.

The implementation should introduce a dedicated manager for registry-local locale TOML. That manager should reuse registry discovery and typed loader knowledge rather than reimplementing schema parsing ad hoc. It should write only under the bundled registry modelo tree or an explicitly supplied contained registry root for tests. It should preserve stable TOML ordering and leave unrelated modelo fragments untouched.

## Rationale

The research showed that modelo schema-local translations already have a runtime backend but lack an authoring authority. Reusing `aeat.locales` gives the schema-local campaign the same operational discipline as codebase `tr(...)` work while respecting the ADR that kept these large catalogues out of eager YAML. A nested modelo sub-surface is the narrowest architecture that unifies localization governance without changing the registry runtime contract.

## Consequences

This decision makes direct registry-local locale TOML editing a transitional smell. Once the CLI lands, schema translation campaigns should use the CLI for all additions, removals, scaffolding, and drift checks.

The CLI will make progress measurable per modelo and per revision, which fits the concurrent campaign model. It will also make broad translation work slower at first because every write must pass validation, but that cost is intentional: broken keys, stale entries, and accidental legal-label mutations should be caught before they reach the registry loader.

The implementation opens a clean path for future quality gates: a focused modelo-local `scaffold --check` can become the pre-commit or CI gate for schema localization without forcing the full registry test suite to be the first drift detector.

## Codification candidates

- **Rule slug:** `modelo-locales-cli-authority`.
  **Rule:** Modelo schema-local translation TOML files must be created, updated, removed, scaffolded, and audited through `python -m aeat.locales modelo ...`; direct hand edits are reserved only for migration commits that introduce the CLI itself.

