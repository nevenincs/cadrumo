---
tags:
  - '#exec'
  - '#aeat-cli-userdocs-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S12'
related:
  - '[[2026-06-04-aeat-cli-userdocs-hardening-plan]]'
---

# `aeat-cli-userdocs-hardening` `W02.P04.S12` execution

Scope: Split `docs/how-to/index.md` into an index plus focused recipes instead of a broad mixed reference-and-recipe page.

## Description

Replaced the broad `docs/how-to/index.md` page with a compact recipe index. The page now routes by task group:

- setup;
- ledger;
- modelo prepare-and-export workflow;
- verify, export, upload, and check records;
- troubleshooting and support.

The page links to existing focused recipes instead of re-authoring command sequences and reference explanations inline. It also names missing handbook surfaces as backlog rather than hiding them inside scattered snippets.

## Outcome

Completed. The non-technical editorial reviewer initially found verify/export/manual-upload insufficiently visible, so the index was revised with a direct `Verify, Export, Upload, and Check Records` section. The reviewer then reported no blockers for closing this step.

## Verification

`uv run pytest src/aeat/entrypoints/cli/test_educational_docs_conformance.py -m docs` passed with 29 tests and 49 deprecation warnings.

After the final privacy wording adjustment, the same command could not collect tests because an unrelated dirty source file, `src/aeat/adapters/persistence/storage/sql/secure_objects.py`, has an import-time syntax error. A local Markdown-only check still confirmed that the two edited pages have no non-ASCII text, no overlong lines, and no broken relative links.

`uv run sphinx-build -n -W -b html docs docs/_build/html` timed out after 10 minutes without producing a content failure. This remains an external build-gate timeout for the shared docs build, not a passed Sphinx gate.
