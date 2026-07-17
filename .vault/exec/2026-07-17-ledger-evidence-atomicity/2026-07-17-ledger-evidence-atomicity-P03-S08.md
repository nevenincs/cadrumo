---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S08'
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
     The S08 and 2026-07-17-ledger-evidence-atomicity-plan placeholders are machine-filled by
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
     The Remove modelo audit replay and every call to the backend replay method while retaining only genuine evidence audit check and ## Scope

- `src/cadrumo/entrypoints/cli/_modelo_audit_cli.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove modelo audit replay and every call to the backend replay method while retaining only genuine evidence audit check

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_audit_cli.py`

## Description

- Remove the `aeat app modelo audit replay` CLI command from `_modelo_audit_cli.py` and drop `replay` from the audit group help default.
- Remove the orphaned `ModeloAuditReplayResult` output schema (`@register_schema("modelo.audit.replay")`) from `_modelo_aux_payloads.py` and its re-export/`__all__` entry from `_modelo_payloads.py`.
- Drop the orphaned `cli.app.modelo.audit.replay_help` locale key across all four catalogues via `python -m cadrumo.locales scaffold`, and retitle `cli.app.modelo.audit.group_help` to `(show/check/export)` in en/es/ca/hu via the locales CLI.

## Outcome

- No `@static` documented-command citation referenced `audit replay`, so documented-command conformance stays green (346 passed; the one failure is the peer-owned `config rekey` .seq, out of this feature's surface). Generated CLI reference/tree/anchor gates regenerate against the live tree and pass. Retained `check` audit verb and the observability `parity_replay_help`. Commit `87f49c5d2f`.

## Notes

- Locale files carried no peer WIP; the diff is scoped to exactly the two audit keys across four catalogues (verified). Pre-existing repo-wide `test_parity` failure (9 codebase keys missing from all four catalogues) is peer drift — it fails identically on HEAD locales and is unrelated to this change.
- `_modelo_aux_payloads.py` is nominally P04/S11's file; removing the replay schema there is the forced consumer sweep of the command removal (the schema is orphaned the moment the command goes), landed in the same green vertical.
