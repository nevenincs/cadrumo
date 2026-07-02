---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S236'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S236 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
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
     The R7-ANNA-D5 default modelo work create --revision to the in-force revision for the supplied --year via registry lookup and ## Scope

- `today operators must run aeat app modelo describe first to find a valid revision id`
- `reduces friction for the common case while preserving explicit override`
- `src/aeat/entrypoints/cli/_modelo.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# R7-ANNA-D5 default modelo work create --revision to the in-force revision for the supplied --year via registry lookup

## Scope

- `today operators must run aeat app modelo describe first to find a valid revision id`
- `reduces friction for the common case while preserving explicit override`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Ground S236 through plan and code RAG searches, then re-read the live work-create lifecycle and registry-revision resolver surfaces.
- Confirm the production resolver already defaults an omitted registry revision to the law-determined revision and treats an explicit `--revision` as an assertion.
- Add a focused CLI integration regression proving a fresh Modelo 131 work unit created without `--revision` carries the registry-selected revision for the supplied year and period.
- Keep adjacent reuse and explicit-mismatch coverage in the same validation run to preserve the intended override/assertion contract.
- Run an independent code review after the regression; the reviewer reported no findings.

## Outcome

S236 is closed as a behavioral ratchet over the already-present lifecycle implementation. Operators can run `work create` with `--modelo`, `--year`, and `--period` only; the created work unit binds to the registry revision selected by the central authority for that filing target. The explicit `--revision` path remains covered as an assertion/refusal path rather than a free override.

## Notes

Validation:

- `uvx vaultspec-rag search "R7 ANNA D5 default modelo work create revision in force supplied year registry lookup" --type vault --doc-type plan --port 8766 --timeout 30` surfaced the current modelo lifecycle and calculation-engine planning trail.
- `uvx vaultspec-rag search "modelo work create registry revision default law determined revision supplied year period" --type code --port 8766 --timeout 30` surfaced `resolve_registry_revision_for_work_target` as the authoritative implementation.
- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py::test_work_create_without_revision_uses_registry_revision_for_supplied_year src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py::test_work_create_without_revision_resumes_existing_visible_target src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py::test_work_create_rejects_revision_that_does_not_cover_filing_year -q` passed with three tests.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py` passed.

Notes:

- Planck was assigned first but hit an external usage-limit error before returning work; the agent slot was closed and the orchestrator completed the narrow regression locally.
- Reviewer Boole reported no findings. Residual risk is limited to oracle independence: the new regression uses the real registry authority to derive the expected revision, so it proves CLI-to-authority binding rather than independently revalidating the registry's legal contents.
