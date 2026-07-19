---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S28'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace auth-cert-recovery-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S28 and 2026-07-17-auth-cert-recovery-custody-plan placeholders are machine-filled by
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
     The Prove recovery status, create, rotate, verify, and recover without serialized mnemonic material and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_config_recovery_lifecycle.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove recovery status, create, rotate, verify, and recover without serialized mnemonic material

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_config_recovery_lifecycle.py`

## Description

- Author `src/cadrumo/entrypoints/cli/tests/test_config_recovery_lifecycle.py`: a real-entrypoint subprocess harness over a real encrypted vault.
- Round-trip status (unenrolled to enrolled with fingerprint), create-refuses-second-enrollment, verify yes/no via `--secrets-stdin`, rotate (old code dies, new code verifies, fingerprint changes), flat recover binding a new passphrase, and profile readability under the recovered passphrase.
- Assert the mnemonic never appears in any CLI stdout/stderr, JSON envelope, or the persisted wrapper file.
- Prove non-interactive create/rotate refuse with the prior envelope byte-identical, strict bounded-JSON stdin refusals, and passphrase-mismatch / wrong-code refusals that leave the vault intact.

## Outcome

Five integration tests green; the enrollment half drives the production `create_recovery_code`/`rotate_recovery_code` operations with a real confirm callback (the CLI create/rotate verbs are TTY-only by design, so the captured harness proves their refusal path).

## Notes

Windows quirk: the `NUL` device reports as a TTY, so the harness pipes stdin (empty when no payload) to get the genuine redirected-stdin condition; an inherited console handle would block on the hidden prompt.
