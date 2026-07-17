---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S15'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-evidence-atomicity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Prove the removed replay and evidence-patch spellings are absent from every source and generated surface and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove the removed replay and evidence-patch spellings are absent from every source and generated surface

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`

## Description

- Flip `test_modelo_audit_verbs_only_register_canonical_four` to `..._three`: move `replay` from the accepted-leaf set into the forbidden-leaf set, proving the audit group now registers only show/check/export and refuses `replay`.
- Add `test_ledger_link_rejects_retired_evidence_id_grammar` proving `ledger link --evidence-id` no longer resolves.
- Correct the stale docstring in `test_root_does_not_register_bare_run_alias` that referenced `aeat app modelo audit replay`.

## Outcome

- The removed replay command and the removed `link --evidence-id` grammar are proven absent at the live CLI surface. `test_root_grammar_invariants.py`: 8 passed (integration). Commit `dc5982eee5`.

## Notes

- This is the source-surface absence proof; the generated CLI reference/tree regenerate against the live surface (already green) and the doc `.seq` citation of `link --evidence-id` was removed in S07. The locale-value absence of `--evidence-id` in the `link` help/error strings is part of the deferred S13 locale cleanup, held own-keys-only until the operator commits the live P04-door locale WIP and the `.yml` goes clean.
