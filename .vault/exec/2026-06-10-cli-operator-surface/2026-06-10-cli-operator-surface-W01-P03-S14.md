---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-10'
step_id: 'S14'
related:
  - "[[2026-06-10-cli-operator-surface-plan]]"
---




# update locale strings via the aeat.locales CLI for any new warning text and regenerate the CLI reference if the flag surface changes

## Scope

- `src/aeat/locales/{en,es,ca,hu}.yml`
- `docs/how-to/troubleshooting.md`

## Description

- Sharpen `cli.root.language_help` in all four locales via `python -m aeat.locales set` to honestly state the flag now covers output **and** help text (e.g. "Language for output and help text (en, es, ca, hu).").
- Rewrite the troubleshooting "Output appears in the wrong language" section to lead with `--language` as the working per-command control (no longer a known limitation), keep `AEAT_OUTPUT_LANGUAGE` as the session-wide control, and note the flag wins over the env var for that command.
- Regenerate the CLI reference build output (docs/cli, gitignored) for the changed help-string text.

## Outcome

Locale gates clean: `python -m aeat.locales scaffold --check` and `audit` report ok for all four catalogues; the parity and translation-honesty pytest gates pass. The CLI command tree / signature is unchanged (no verb or option added/removed — only the `--language` help string text and the `main()` pre-parse changed), so the reference delta is help-text-only; the drift gate passes after regeneration. The troubleshooting page now documents the honest contract.

## Notes

No new warning text was needed (make-it-work shipped, not warn-only). No flag surface changed, so no `apidocs scaffold` source-tree change is implicated; the new `_language_argv.py` is a private underscore module excluded from stub generation (apidocs audit: 0 missing/orphan/stale). All four locale edits went through the `aeat.locales` CLI, never a hand-edited `.yml`.
