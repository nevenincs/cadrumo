---
name: aeat-locales-cli
---

# AEAT locale catalogue CLI

## Rule

Perform all locale-catalogue work through the `cadrumo.locales` CLI; never
hand-edit the `src/cadrumo/locales/{en,es,ca,hu}.yml` files or the
`_intentional_identical.json` allowlist directly. Verbs: `python -m cadrumo.locales
set LOCALE KEY VALUE` / `remove LOCALE KEY` (individual leaves), `scaffold` (align
catalogues to codebase keys), `scaffold --check` (drift gate), `audit`
(codebase-to-locale health).

## Why

The four catalogues are not free-form YAML: `test_parity.py` requires every
codebase key to exist in every locale and every locale to carry the same key set,
and `test_locale_translation_honesty.py` ratchets keys left identical to English,
allowing an untranslated string only when `_intentional_identical.json` records it
with an explicit reason. Hand-editing a `.yml` bypasses these guarantees — it lands
a key in one locale only (parity break), lets a stale key outlive its removed
reference (drift), or slips an untranslated string past the honesty ratchet. The
CLI maintains parity across all four files in one operation. Locale-surface sibling
of `aeat-docs-scaffolding-cli`.

## How

- **Good:** translate one string with `python -m cadrumo.locales set es
  "cli.config.google.help" "Configura las credenciales de Google"` (writes the leaf,
  preserves parity); after adding/removing a `tr(...)` call run
  `python -m cadrumo.locales scaffold` so every catalogue gains/drops the key, then
  `scaffold --check` confirms zero drift. A legitimately-identical string (brand
  name, bare modelo code) is registered through the CLI honesty-gate process that
  records `_intentional_identical.json` with a reason.
- **Bad:** opening `es.yml` in an editor to add a key (lands in one locale, trips
  parity, skips the ratchet); or hand-appending to `_intentional_identical.json` to
  silence the honesty gate for a string you simply did not translate — the allowlist
  is for deliberately-identical strings with a stated reason, not a mute button.

## Source

Operator directive 2026-06-02 (docs-educational-surface campaign,
`chore/eliminate-shims`), alongside `aeat-docs-scaffolding-cli`. Backing gates:
`test_parity.py`, `test_locale_translation_honesty.py`.
