---
name: modelo-locales-cli-authority
---

# Modelo Locale CLI Authority

## Rule

Modelo localization values — Modelo and revision titles/official names, construct
titles, and every casilla `label`/`help` string — live ONLY in the four shared
runtime catalogues at `src/cadrumo/locales/{es,en,ca,hu}.yml`, under derived
dotted keys (`modelo.schema.<modelo-id>.revision.<revision>.casilla.<casilla-id>.label`
and siblings), resolved through `resolve_modelo_localization` /
`lookup_translation_entry`. Manage them through the STANDARD `cadrumo.locales`
CLI (`scaffold`, `set`, `set-batch`, `remove`, `audit`, `status`) — the same
authority as any other application key — never by hand-editing the catalogue
YAML files. There is no `python -m cadrumo.locales modelo ...` verb family and
no per-modelo registry-local `locales/*.toml` file: both were retired by the
migration below, and neither may be reintroduced or recreated.

## Why

The prior architecture (a `modelo` CLI subcommand authoring
`registry/aeat/modelos/<id>/revisions/<rev>/locales/*.toml` fragments, with
Spanish schema-local TOML deliberately absent) was governed by ADR
`2026-06-11-modelo-locales-cli-adr`. That ADR is SUPERSEDED by the accepted
`2026-08-04-modelo-localization-cascade-adr`, whose D1 makes the four shared
catalogues the sole text authority for every Modelo/revision/casilla
presentation value and whose D7 retires the `modelo` file-authoring commands
and `ModeloLocaleManager` after cutover. The migration ran to completion:
`git log` shows 44 commits authoring real per-modelo `locales/*.toml` content
under the registry tree, and a final commit (`ced27b5a59`, "checkpoint
root-only Modelo localization migration", 2026-08-05) deleting the last of
them — the current tree carries zero files under
`registry/aeat/modelos/**/locales/**`, and `python -m cadrumo.locales --help`
carries no `modelo` command at all (`No such command 'modelo'`).

This correction exists because the retirement was never reflected here: this
rule kept citing the superseded ADR and instructing agents to use tooling that
no longer exists and to author files the accepted architecture deliberately
deletes — a `firmware-reference-parity`-class staleness in an always-on rule,
discovered while investigating why `es.yml` carries ~33,500 casilla-schema
keys (~86% of its bytes) forcing a real per-process YAML-parse cost. That
content is not misplaced; it is the correct, current, load-bearing design.

## How

- Good: run `python -m cadrumo.locales scaffold es` (or `set` /
  `set-batch` for a single leaf) exactly as for any other application key —
  the derived `modelo.schema.*` keys are ordinary catalogue entries once
  compiled by the registry loader (`_modelo_localization.py`), with no
  modelo-specific verb.
- Good: `ModeloDefinition.title` / `.get_title(locale)`, `ModeloRevision.label`
  / `.get_label(locale)`, and a compiled `CasillaDefinition`'s
  `localization_keys` all resolve through `resolve_modelo_localization`
  against these same four catalogues; Spanish (`es`) is the mandatory,
  `required=True` source for titles and official names.
- Good: a rule, persona, or note that mentions the pre-migration layout states
  plainly that it is retired — the old layout is still visible in git history,
  so a future reader should learn it was deliberately removed, not that it is
  a gap to fill in.
- Bad: authoring or expecting `python -m cadrumo.locales modelo scaffold|set|coverage`
  — the verb does not exist.
- Bad: creating `registry/aeat/modelos/<id>/revisions/<rev>/locales/*.toml` —
  the accepted architecture forbids any locale file beneath the Modelo
  registry tree; recreating one reintroduces the pre-migration layout the
  cutover deleted.
- Bad: hand-editing `es.yml`/`en.yml`/`ca.yml`/`hu.yml` directly instead of
  through the `cadrumo.locales` CLI (see `aeat-locales-cli`, which still
  governs these four files in full).

## Source

Superseded: ADR `2026-06-11-modelo-locales-cli-adr` (no longer authoritative).
Superseding, current authority: ADR `2026-08-04-modelo-localization-cascade-adr`
(D1, D7, D9). Companion: `aeat-locales-cli` (the standard four-catalogue CLI
this rule now defers to entirely).
