---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S23'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S23 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Add real-filesystem tests for fresh Cadrumo state and explicit old-state refusal and ## Scope

- `src/cadrumo/adapters/persistence/storage/tests/test_cadrumo_state_identity_acceptance.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add real-filesystem tests for fresh Cadrumo state and explicit old-state refusal

## Scope

- `src/cadrumo/adapters/persistence/storage/tests/test_cadrumo_state_identity_acceptance.py`

## Description

- Compose the production installed-root, database, encrypted session, namespace, and sealed-archive boundaries in one fresh-state acceptance proof.
- Exercise recognizable former root, database, session, namespace, and bundle states through their production refusal gates.
- Preserve former sentinel bytes and assert that no corresponding canonical state is created.

## Outcome

Fresh state resolves beneath the Cadrumo application root, creates only `cadrumo.db`, derives the `.cadrumo` authentication-session key, writes under the Cadrumo namespace, and round-trips a Cadrumo-marked sealed bundle. Former-state probes are refused without mutation, adoption, fallback, or canonical successor creation.

The clean-filesystem focused run passed ten tests: both new integration scenarios plus the nearest root, database, session, namespace, and bundle boundary tests. Ruff, formatting, and scoped diff checks passed.

## Notes

The integration module deliberately relies on existing production helpers and the established real encrypted runtime harness. It does not repeat exhaustive field-level assertions already owned by S18-S22 tests.

Formal review initially found that canonical session persistence and post-namespace-refusal absence needed stronger proof. The test now round-trips the session through real encrypted storage, inspects raw persisted namespaces, and proves no former or canonical counterpart row was created; re-review closed both findings with no new issues. The final isolated rerun passed both integration scenarios.
