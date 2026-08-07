---
name: modelo-locales-cli-authority
trigger: always_on
---

# Modelo localization lives in the shared runtime catalogues

Modelo and revision titles and official names, construct titles, and every
casilla `label` and `help` string live ONLY in the four shared runtime catalogues
at `src/cadrumo/locales/{es,en,ca,hu}.yml`, under derived dotted keys
(`modelo.schema.<modelo-id>.revision.<revision>.casilla.<casilla-id>.label` and
siblings), resolved through `resolve_modelo_localization` /
`lookup_translation_entry`.

Manage them through the STANDARD `cadrumo.locales` CLI — the same authority as
any other application key, governed by `aeat-locales-cli`. Spanish is the
mandatory, required source for titles and official names.

**There is no `python -m cadrumo.locales modelo ...` verb family and no
per-modelo registry-local `locales/*.toml` file.** Both were retired; neither may
be reintroduced or recreated.

The four shared catalogues are the sole text authority for every Modelo,
revision and casilla presentation value. Casilla-schema keys dominate the Spanish
catalogue by volume, and that content is load-bearing, not misplaced.

## How

- **Good:** `ModeloDefinition.get_title(locale)`,
  `ModeloRevision.get_label(locale)`, and a compiled `CasillaDefinition`'s
  `localization_keys` all resolve through `resolve_modelo_localization` against
  these catalogues. The derived `modelo.schema.*` keys are ordinary catalogue
  entries once compiled by the registry loader, with no modelo-specific verb.
- **Bad:** expecting `python -m cadrumo.locales modelo scaffold|set|coverage` —
  the verb does not exist.
- **Bad:** creating `registry/aeat/modelos/<id>/revisions/<rev>/locales/*.toml` —
  the accepted architecture forbids any locale file beneath the Modelo registry
  tree.

Source: ADR `2026-08-04-modelo-localization-cascade-adr` (D1, D7, D9),
superseding `2026-06-11-modelo-locales-cli-adr`.
