---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S03'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace data-output-standardization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-13-data-output-standardization-plan placeholders are machine-filled by
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
     The Delete the dormant consumer-less browser-trace dir field pair and sweep references and ## Scope

- `src/cadrumo/core/config.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Delete the dormant consumer-less browser-trace dir field pair and sweep references

## Scope

- `src/cadrumo/core/config.py`

## Description

- Delete the dormant `cadrumo_submission_browser_trace_dir` and `cadrumo_status_browser_trace_dir` field definitions from `config.py`; both had no consumer anywhere in the package and shared one duplicate default directory.
- Remove the pair from the state-root derivation table and from the `_normalize_repo_relative_paths` validator tuple.
- Drop the two lines from `env/.env.example` and the two rows from `docs/reference/environment-overrides.md` (regenerated to match generator output byte-for-byte).
- Remove the one dead test override that constructed a `Settings` with `cadrumo_submission_browser_trace_dir` in the submission-engine export test (the engine never reads the field).

## Outcome

The duplicate dormant browser-trace field pair is gone. Gates: collection clean repo-wide (no errors); the settings/env-parity suite, the state-root derivation tests, the submission-engine export suite, and the env-reference freshness + parity gates all pass; ruff clean on the touched Python files. A grep for both field names across the package returns no matches.

## Notes

The AEAT-prefixed exports `AEAT_SUBMISSION_BROWSER_TRACE_DIR` / `AEAT_STATUS_BROWSER_TRACE_DIR` in the agent persona harness script are already-dead legacy-prefixed exports (the settings model reads the `CADRUMO_` names, never these) and are left untouched as out-of-scope harness scaffolding. If a browser-trace capture writer is reintroduced later, it lands a fresh field at that time per the no-dormant discipline.
