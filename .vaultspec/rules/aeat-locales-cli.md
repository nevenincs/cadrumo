---
name: aeat-locales-cli
---

# AEAT locale catalogue CLI

## Rule

Perform all locale-catalogue work through the `aeat.locales` CLI; never
hand-edit the `src/aeat/locales/{en,es,ca,hu}.yml` files or the
`_intentional_identical.json` allowlist directly. Use `python -m aeat.locales
set LOCALE KEY VALUE` and `python -m aeat.locales remove LOCALE KEY` for
individual string leaves, `python -m aeat.locales scaffold` to align the
catalogues with the concrete translation keys in the codebase, `python -m
aeat.locales scaffold --check` as the drift gate, and `python -m aeat.locales
audit` for a codebase-to-locale health report.

## Why

The four locale catalogues are not free-form YAML: the parity gates
(`test_parity.py`) require every codebase translation key to exist in every
locale and every locale to carry the same key set, and the translation-honesty
gate (`test_locale_translation_honesty.py`) ratchets the number of keys left
identical to English, allowing an untranslated string only when
`_intentional_identical.json` records it with an explicit reason. Hand-editing a
`.yml` bypasses these structural guarantees: it is how a key lands in one locale
but not the other three (inter-locale parity break), how a stale key outlives its
removed codebase reference (codebase-to-locale drift), and how an untranslated
string slips past the honesty ratchet. The CLI maintains key parity across all
four files in one operation and keeps the allowlist honest, so the gates stay
green. This rule is the locale-surface sibling of `aeat-docs-scaffolding-cli`
(the generated-documentation CLI) and complements the audience-separation
mandate that user-facing docs must not re-author or reuse locale keys.

## How

- **Good:** translating one string runs `python -m aeat.locales set es
  "cli.config.google.help" "Configura las credenciales de Google"`, which writes
  the leaf and preserves key parity; a follow-up `scaffold --check` and `audit`
  exit clean.
- **Good:** after adding or removing a `tr(...)` call in the code, run
  `python -m aeat.locales scaffold` so every catalogue gains the new key (or
  drops the retired one) in the same change, then `scaffold --check` confirms zero
  drift before commit.
- **Good:** a string that is legitimately identical across locales (a brand name,
  a bare modelo code) is registered through the CLI / honesty-gate process that
  updates `_intentional_identical.json` with a reason — never by silently leaving
  it untranslated.
- **Bad:** opening `es.yml` in an editor to add a key. It almost always lands in
  one locale only, tripping the inter-locale parity gate, and skips the honesty
  ratchet entirely.
- **Bad:** hand-appending an entry to `_intentional_identical.json` to silence the
  honesty gate for a string you simply did not translate. The allowlist is for
  deliberately-identical strings with a stated reason, not a mute button.
- **Bad:** running the full test suite to discover locale drift instead of
  `aeat.locales audit` / `scaffold --check`, which report it instantly.

## Source

Operator directive recorded 2026-06-02 during the docs-educational-surface
campaign on the `chore/eliminate-shims` branch, authored alongside
`aeat-docs-scaffolding-cli` to give the locale surface the same
CLI-is-authoritative discipline. Backing gates: `test_parity.py`
(codebase-to-locale and inter-locale parity), `test_locale_translation_honesty.py`
(the `_intentional_identical.json` untranslated-ceiling ratchet).
