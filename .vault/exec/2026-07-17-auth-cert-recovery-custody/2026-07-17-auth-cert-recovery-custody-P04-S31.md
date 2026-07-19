---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S31'
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
     The S31 and 2026-07-17-auth-cert-recovery-custody-plan placeholders are machine-filled by
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
     The Align bootstrap and repair-policy inventories with the recovery family and flat recover exception and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Align bootstrap and repair-policy inventories with the recovery family and flat recover exception

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py`

## Description

- Align `_bootstrap_exempt.py` with the recovery family: the `config recovery` prefix and flat `config recover` replace the retired `show-recovery`/`verify-recovery` entries.
- Extend the repair-policy catalog with `config recovery status/create/rotate/verify` surfaces and update `test_repair_policy_coverage.py` so the custody subgroups (`config recovery`, `config passphrase`) are policy-relevant in full.
- Teach the coverage gate's AST walker to resolve `add_typer(child)` mounts through the child's `typer.Typer(name=...)` constructor, closing the latent gap that hid the passphrase subgroup from discovery.

## Outcome

Bootstrap and repair-policy inventories match the live custody grammar; the discovery-vs-catalog equality gate is green including the passphrase family.

## Notes

None.
