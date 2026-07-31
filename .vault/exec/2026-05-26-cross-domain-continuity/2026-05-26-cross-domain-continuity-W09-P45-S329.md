---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-17'
body_hash: 'sha256:bf1937b5bf84542d81243c8c1a2013d98ab4f4cbe8396f5a1b51084dd86a1d98'
step_id: 'S329'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R9-ZSOFIA-B identify and localise commands where --language flag is accepted but has no effect on output

## Scope

- `config profile show config auth status modelo work calculate (closing prose only) confirmed broken`
- `the parity test S144 must catch these as ineffective-flag cases not just absent-flag cases`
- `src/aeat/entrypoints/cli/`

## Description

- Assess-first: confirmed each broken sub-case at HEAD before authoring. Proved the `--language` mechanism itself works (a no-active-profile refusal already renders Hungarian) — the flag is dead only where output strings skip `tr()`.
- Localised `config auth status`: prepend a locale-driven operator verdict line (configured / configured-but-no-session / unconfigured) via `tr()`, keeping the tab-separated `key`/`value` lines as stable machine field identifiers (they mirror the JSON envelope).
- Localised `config profile show`: prepend a locale-driven record-validity verdict line (valid / invalid+count / tombstoned); keep the `record_validity` and field-key/`value` lines as machine identifiers.
- Authored 6 keys x 4 locales (genuine es/ca/hu, not English copies) through the `aeat.locales` CLI (`scaffold` + `set`).
- Extended the S144 parity gate (`test_output_language_parity.py`): new effectiveness test runs a command in `en` vs `hu` (leaf and root flag) and fails if output is byte-identical — catching the ineffective-flag class, not just the absent-flag class. Anchored on the stateless `config auth status` surface.
- Sub-case `modelo work calculate` (closing prose): VERIFY-CLOSE only, resolved-at-HEAD — the closing confirmation is `tr("cli.app.modelo.work.calculate_saved")` and `hu.yml` already carries a genuine Hungarian translation, so it localises correctly. No code change.

## Outcome

Landed as commit `1b326f1edb` (`fix(cli): localise config auth status / profile show output (S329)`), 7 files, explicit-pathspec (only mine despite ~55 peer-staged files in the shared index). `--language hu` / `--output-language hu` now produce visibly Hungarian verdict lines on both commands; en / hu / es outputs differ. Gates green: ruff, ty, `test_output_language_parity` (6), locale parity + honesty (22), `scaffold --check` clean.

Design decision (coordinator-ratified, option B): the tab-separated field-key/value lines are the text mirror of the JSON envelope and key on stable machine identifiers, so localising them would diverge human text from the machine schema and break scripts/operators — kept as documented technical identifiers per the sibling S330 precedent. The flag becomes visibly effective through the localised operator-facing verdict prose instead.

## Notes

- Five pre-existing, owner-distinct integration failures in `test_certificate.py` / `test_apoderado.py` (`expected CliRefusedBoundaryError, got SystemExit: 2`) were observed during the surface test run. Proven pre-existing via a sanctioned HEAD-swap (identical five failures against HEAD versions of the touched files; the two edited files pass in isolation). Ordering-dependent refusal-decoration drift in the certificate/apoderado suite, unrelated to localisation — flagged as inventory, not this Step's regression.
