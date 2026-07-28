---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S169'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S169 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Regenerate data-access sequence goldens from real accepted commands and ## Scope

- `docs/_sequences/how-to/protect-data-access/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Regenerate data-access sequence goldens from real accepted commands

## Scope

- `docs/_sequences/how-to/protect-data-access/`

## Description

- Enumerated the eight sequence contracts under `docs/_sequences/contracts/how-to/protect-data-access/`.
- Confirmed that seven of the eight are `@static`: passphrase-change, recover, recovery-create, recovery-rotate, recovery-verify (all `interactive-tty` — the sandbox cannot answer passphrase or recovery-code prompts), recovery-status (`nondeterministic-output` — prints a recovery path beside the sandbox root which the path normaliser does not tokenise), and reset (`nondeterministic-output` — emits a fresh 64-hex operation id per run which `GOLDEN_MASK_FIELDS` does not mask). One sequence is executable: `protect-data-access-logout`.
- Ran `python -m dev.docs.sequences refresh --page how-to/protect-data-access` to regenerate the executed golden.
- Ran `python -m dev.docs.sequences check --page how-to/protect-data-access` to verify the refreshed golden passes the sequence contract gate.

## Outcome

Verdict: SATISFIED.

Refresh command: `uv run --no-sync python -m dev.docs.sequences refresh --page how-to/protect-data-access`.
Output: `1 golden(s) rewritten`. The one executed sequence (`protect-data-access-logout`) was refreshed. The seven `@static` contracts are legitimately unexecutable and produce no golden; their `@blocked` annotations document the exact blocker for each.
Check command: `uv run --no-sync python -m dev.docs.sequences check --page how-to/protect-data-access`.
Output: `cli-sequence goldens: clean`. Exit code 0. HEAD at run time: `9c4b780e1aed5c41938e16eaed2eccdcbddd3cfd`.

Static inventory (all seven verified against their contract files):

- `protect-data-access-passphrase-change`: `@blocked interactive-tty` — `aeat config passphrase change` refuses when no interactive terminal is available.
- `protect-data-access-recover`: `@blocked interactive-tty` — `aeat config recover` refuses when no interactive terminal is available.
- `protect-data-access-recovery-create`: `@blocked interactive-tty` — enrollment shows the recovery code once on an interactive terminal only.
- `protect-data-access-recovery-rotate`: `@blocked interactive-tty` — enrollment shows the recovery code once on an interactive terminal only.
- `protect-data-access-recovery-verify`: `@blocked interactive-tty` — `aeat config recovery verify` refuses when no interactive terminal is available.
- `protect-data-access-recovery-status`: `@blocked nondeterministic-output` — prints a recovery path beside the sandbox root; the path normaliser does not tokenise it.
- `protect-data-access-reset`: `@blocked nondeterministic-output` — `aeat config reset start --yes` emits a fresh 64-hex operation id per run; `GOLDEN_MASK_FIELDS` does not mask it.

## Notes

None. The static inventory exhausts the eight contracts; no golden is missing for an executable sequence.
