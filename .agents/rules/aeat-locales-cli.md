---
name: aeat-locales-cli
trigger: always_on
---

# AEAT locale catalogue CLI

Perform all locale work through the `cadrumo.locales` CLI; never hand-edit the
`src/cadrumo/locales/{en,es,ca,hu}.yml` files or the `_intentional_identical.json`
allowlist directly. Verbs: `set LOCALE KEY VALUE` / `remove LOCALE KEY` for
individual leaves, `scaffold` to align catalogues to codebase keys,
`scaffold --check` as the drift gate, and `audit` for a health report.

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

Modelo, revision and casilla presentation text lives in these same catalogues
under derived keys and is managed with these same verbs — see
`modelo-locales-cli-authority`.

## How

- **Good:** `python -m cadrumo.locales set es "cli.config.google.help" "..."`;
  after adding or removing a `tr(...)` call, run `scaffold` then
  `scaffold --check`.
- **Bad:** opening a `.yml` to add a key; or hand-appending to
  `_intentional_identical.json` to silence the honesty gate for a string you
  simply did not translate — the allowlist is for deliberately-identical strings
  with a stated reason, not a mute button.

Gates: `test_parity.py`, `test_locale_translation_honesty.py`.
