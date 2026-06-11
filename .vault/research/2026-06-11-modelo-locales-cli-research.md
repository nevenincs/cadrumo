---
tags:
  - '#research'
  - '#modelo-locales-cli'
date: '2026-06-11'
related:
  - '[[2026-06-08-registry-localization-backend-adr]]'
  - '[[2026-06-11-registry-schema-localization-research]]'
---

# `modelo-locales-cli` research: `aeat.locales authority for modelo schema localization`

This research grounds the pivot from direct registry-local TOML edits to an `aeat.locales`-managed workflow for modelo schema translations. The goal is to bring the same command discipline used for core `tr(...)` catalogues to registry-local casilla labels and help strings while preserving the legal Spanish schema invariants.

## Findings

- The existing core locale workflow is centered on `python -m aeat.locales`. Its `audit`, `scaffold`, `set`, and `remove` verbs delegate to `LocaleManager`, preserve key parity across `src/aeat/locales/*.yml`, and keep developers from hand-editing the eager application locale catalogues.
- Registry-local schema translation already has a separate runtime mechanism. `CasillaDefinition` carries `localized_labels` and `localized_help`; the registry loader reads `locales/<locale>.toml` beside modelo or revision data, validates translation keys against real `continuidad_id` or `casilla_id`, injects the localized maps into casillas, and includes locale TOML files in registry fingerprints.
- The missing layer is an authoring CLI. Current direct edits to files such as revision-local `en.toml`, `ca.toml`, and `hu.toml` can satisfy the loader, but they bypass the ergonomics and guardrails that the project already requires for codebase `tr(...)` keys.
- The existing `aeat.locales` CLI should be extended rather than paralleled. A second command family would violate the local rule that locale-catalogue work goes through `aeat.locales`, and a separate root would make the operator remember which localization surface is governed by which tool.
- Modelo schema translations are not ordinary global `tr(...)` keys. They are registry-local, lazily loaded, potentially large, and keyed by either revision-local `casilla_id` or modelo-wide `continuidad_id`. The CLI therefore needs a sub-surface that writes TOML under the registry tree rather than YAML under `src/aeat/locales`.
- The CLI should support at least audit, scaffold, set, and remove semantics for model-local localization. Audit must report missing labels/help by modelo, revision, locale, and key. Scaffold must create or align locale TOML skeletons without overwriting translated values. Set/remove must validate containment, locale, modelo, revision, field kind, and target key before writing.
- Completion tracking needs to be per modelo and revision. The current coverage evidence shows small complete slices are feasible, but large modelos require incremental rollout; the CLI should be able to emit coverage summaries so campaigns can coordinate without direct file inspection.

