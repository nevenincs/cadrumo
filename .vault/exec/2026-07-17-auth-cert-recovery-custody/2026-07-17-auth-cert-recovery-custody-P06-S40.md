---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S40'
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
     The S40 and 2026-07-17-auth-cert-recovery-custody-plan placeholders are machine-filled by
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
     The Prove the removed auth, certificate, and recovery spellings are absent from every source and generated surface and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove the removed auth, certificate, and recovery spellings are absent from every source and generated surface

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`

## Description

- Extend `test_root_grammar_invariants.py`: the retired spellings (`rekey`, `show-recovery`, `verify-recovery`) do not resolve; no recovery verb accepts a mnemonic/passphrase argv option; `config recovery` mounts exactly status/create/rotate/verify.
- Add a source-and-docs sweep asserting the retired spellings (including `--recovery-key` and `config rekey`) are absent from the Python tree, the four locale catalogues, the operator docs, and the sequence contracts, exempting only the rejection-probe tests that exist to prove refusal.

## Outcome

Grammar invariants green; the sweep caught and drove out the last stragglers in the master-key error texts, storage tests, and locale copy.

## Notes

None.
