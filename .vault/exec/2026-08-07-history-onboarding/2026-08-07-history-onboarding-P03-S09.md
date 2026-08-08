---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:c33a3fec56f5bede2b6e48da8db9bcdafe5e1e5a0fa0c7100654542287a49aac'
step_id: 'S09'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace history-onboarding with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-08-07-history-onboarding-plan placeholders are machine-filled by
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
     The add the aeat app live filed pull-all verb, verified by test_documented_command_conformance.py and a new JSON-schema conformance case and ## Scope

- `src/cadrumo/entrypoints/cli/_app_live.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add the aeat app live filed pull-all verb, verified by test_documented_command_conformance.py and a new JSON-schema conformance case

## Scope

- `src/cadrumo/entrypoints/cli/_app_live.py`

## Description

- Add the `filed pull-all` verb emitting the onboarding result plus its advisories.
- Add the conformance cases for the registered schema.

## Outcome

The verb assembles its notices from the authorities beside the run model rather
than re-deriving them, so the asymmetry rule and the INFO-not-WARNING judgement
are each decided once. It adds one notice of its own: a WARNING naming every pair
that REFUSED, stating explicitly that a refusal is not evidence nothing was filed.

The envelope command identifier and the schema key are `app.live.filed.pull_all`,
matching the canonicalisation the CLI leaf walk performs on a hyphenated verb —
the sibling `pull_sources` key confirms the convention.

## Verification

uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py -q -n0 -m "unit or integration"
    (within the closeout run below; 1147 passed overall)

The leaf-schema gate caught the key mismatch on first run, naming both sides:
`app.live.filed.pull_all` missing a schema and `app.live.filed.pull-all` an orphan
registry key.

## Notes

The envelope round-trip and no-bespoke-notice-field cases are written out
explicitly rather than left to the shared parametrised gates, for the reason now
rowed as `P04.S30`: those gates parametrise over the schema registry as populated
at COLLECTION time, and the conformance module imports only the config payload
modules, so the entire `app.*` family never reaches them.
