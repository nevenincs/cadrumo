---
name: aeat-locales-cli
trigger: always_on
---

# AEAT locale catalogue CLI

Perform all locale work through the `dev.locales` CLI; never hand-edit the
`src/cadrumo/locales/{en,es,ca,hu}/` shard trees or the `_intentional_identical.json`
allowlist directly. Verbs: `set LOCALE KEY VALUE` / `remove LOCALE KEY` for
individual leaves, `scaffold` to align catalogues to codebase keys,
`scaffold --check` as the drift gate, and `audit` for a health report.

The catalogue DATA ships under `src/cadrumo/locales/` because the renderer loads
it at runtime, but the maintenance TOOLING is not in the package: it lives at
`dev/locales/`, so the module path is `dev.locales` and the tool runs from a
repository checkout only. There is no `cadrumo.locales` CLI.

The four catalogues are not free-form YAML: a parity gate requires every codebase
key to exist in every locale and every locale to carry the same key set, and an
honesty ratchet allows an untranslated string only when
`_intentional_identical.json` records it with an explicit reason. Hand-editing
lands a key in one locale only, lets a stale key outlive its removed reference,
or slips an untranslated string past the ratchet.

**A new `tr()` key needs a REAL value in all four catalogues.** There is no
sanctioned untranslated state: the scaffold's documented self-referencing
placeholder (value equals key) is refused by a shipped gate, and omitting `ca` or
`hu` trips the parity check. Both escapes are red. When a task says "en/es only,
someone else will translate", obtain the `ca` and `hu` strings before running
`set`, or the tree goes red the moment anything sweeps your working copy.

## Modelo localization lives in these same catalogues

Modelo and revision titles and official names, construct titles, and every
casilla `label` and `help` string live ONLY in these four catalogues, under
derived dotted keys
(`modelo.schema.<modelo-id>.revision.<revision>.casilla.<casilla-id>.label` and
siblings), resolved through `resolve_modelo_localization` /
`lookup_translation_entry`, and managed with these same standard verbs. Spanish
is the mandatory, required source for titles and official names.

**There is no `python -m dev.locales modelo ...` verb family and no
per-modelo registry-local `locales/*.toml` file.** Both were retired; neither may
be reintroduced or recreated. Casilla-schema keys dominate the Spanish catalogue
by volume, and that content is load-bearing, not misplaced.

## How

- **Good:** `python -m dev.locales set es "cli.config.google.help" "..."`;
  after adding or removing a `tr(...)` call, run `scaffold` then
  `scaffold --check`.
- **Good:** `ModeloDefinition.get_title(locale)`,
  `ModeloRevision.get_label(locale)` and a compiled `CasillaDefinition`'s
  `localization_keys` all resolve through `resolve_modelo_localization` against
  these catalogues.
- **Bad:** opening a `.yml` to add a key; or hand-appending to
  `_intentional_identical.json` to silence the honesty gate for a string you
  simply did not translate — the allowlist is for deliberately-identical strings
  with a stated reason, not a mute button.
- **Bad:** expecting `python -m dev.locales modelo scaffold|set|coverage` —
  the verb does not exist.
- **Bad:** creating `registry/aeat/modelos/<id>/revisions/<rev>/locales/*.toml`.

Gates: `test_parity.py`, `test_locale_translation_honesty.py`. Source: ADR
`2026-08-04-modelo-localization-cascade-adr`, superseding
`2026-06-11-modelo-locales-cli-adr`; tooling location per
`2026-08-07-dev-harness-bleed-adr`.
