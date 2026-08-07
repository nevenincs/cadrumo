---
name: modelo-locales-cli-authority
trigger: always_on
---

# Modelo localization lives in the shared runtime catalogues

## Rule

Modelo localization values — Modelo and revision titles and official names,
construct titles, and every casilla `label` and `help` string — live ONLY in the
four shared runtime catalogues at `src/cadrumo/locales/{es,en,ca,hu}.yml`, under
derived dotted keys
(`modelo.schema.<modelo-id>.revision.<revision>.casilla.<casilla-id>.label` and
siblings), resolved through `resolve_modelo_localization` /
`lookup_translation_entry`.

Manage them through the STANDARD `cadrumo.locales` CLI (`scaffold`, `set`,
`set-batch`, `remove`, `audit`, `status`) — the same authority as any other
application key — never by hand-editing the catalogue YAML.

**There is no `python -m cadrumo.locales modelo ...` verb family and no
per-modelo registry-local `locales/*.toml` file.** Both were retired; neither
may be reintroduced or recreated.

## Why

ADR `2026-08-04-modelo-localization-cascade-adr` (D1, D7, D9) makes the four
shared catalogues the sole text authority for every Modelo, revision and casilla
presentation value, and retires the file-authoring commands and their manager
after cutover. It supersedes `2026-06-11-modelo-locales-cli-adr`, whose
registry-local TOML fragments no longer exist anywhere in the tree.

The catalogues are correspondingly large — casilla-schema keys dominate `es.yml`
by volume — and that content is load-bearing, not misplaced.

## How

- **Good:** `python -m cadrumo.locales scaffold es`, or `set` / `set-batch` for
  a single leaf, exactly as for any other application key. The derived
  `modelo.schema.*` keys are ordinary catalogue entries once compiled by the
  registry loader.
- **Good:** `ModeloDefinition.get_title(locale)`,
  `ModeloRevision.get_label(locale)`, and a compiled `CasillaDefinition`'s
  `localization_keys` all resolve through `resolve_modelo_localization` against
  these same catalogues. Spanish is the mandatory, required source for titles
  and official names.
- **Bad:** expecting `python -m cadrumo.locales modelo scaffold|set|coverage` —
  the verb does not exist.
- **Bad:** creating `registry/aeat/modelos/<id>/revisions/<rev>/locales/*.toml`
  — the accepted architecture forbids any locale file beneath the Modelo
  registry tree.
- **Bad:** hand-editing the four catalogue files directly.

## Source

ADR `2026-08-04-modelo-localization-cascade-adr`, superseding
`2026-06-11-modelo-locales-cli-adr`. Companion: `aeat-locales-cli`, which
governs these four files in full.
