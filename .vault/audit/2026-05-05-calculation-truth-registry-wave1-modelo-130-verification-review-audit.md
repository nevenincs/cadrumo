---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-wave1-step1-exec]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-adr]]'
  - '[[2026-05-04-live-filing-data-capture-adr]]'
---



# `calculation-truth-registry` Code Review

CTR-M130-001 | MEDIUM | Modelo 130 submitted-file verification still self-selects the computed assertion surface

`src/aeat/adapters/outbound/aeat/sede/test_declarations.py` now resolves the prior-year binding through `resolve_previous_filing_bindings_from_filed_declarations`, which is the right behaviour boundary. However, the test still derives both `input_values` and `computed_casillas` from `snapshot.revision.casillas` before comparing calculated values with observed filed values. If the Modelo 130 registry accidentally reclassifies a computed casilla as manual, drops a computed formula, or removes a casilla from the computed set, this live verification can stop asserting that filed casilla instead of failing. That leaves part of the test coupled to the metadata it is meant to verify. The test should assert the expected Modelo 130 computed casilla set explicitly, including `03`, `04`, `07`, `09`, `11`, `12`, `13`, `14`, `17`, and `19`, before comparing filed values to calculated values.

Resolution: fixed. The submitted-file calculation test now asserts the exact Modelo 130 computed-casilla set before comparing the filed values with the registry calculation output.

CTR-M130-002 | LOW | Modelo 111 live-file tests are included in the Modelo 130 bounded step

`src/aeat/adapters/outbound/aeat/sede/test_declarations.py` adds Modelo 111 submitted-file and declaration-PDF assertions that load the Modelo 111 registry snapshot and committed Modelo 111 submitted-file fixture. Those assertions pass, but they couple this Modelo 130 verification step to a Modelo 111 surface owned by another agent. This should be moved to the Modelo 111 execution/review surface or separated from the Modelo 130 step so this bounded review does not create cross-wave ownership drift.

Resolution: accepted as a scope note. No additional Modelo 111 edits were made in this correction pass because another agent owns Modelo 111 work. The Modelo 130 plan and execution record do not mark Modelo 111 progress.

CTR-M130-003 | LOW | Metadata cleanup misses a non-Python PDF fixture manifest

`tests/fixtures/pdf_corpus/l1_public_anchors/_manifest.json` still contains development-process metadata in its `description` value: `EPIC #305 cluster C`. The execution record's metadata scan only covers Python files under `src\aeat` and `tests`, so this JSON fixture remains outside the cleanup gate even though `tests/fixtures/pdf_corpus/**` is in the reviewed scope. The cleanup check should include fixture metadata files, and the manifest description should be made project-state neutral.

Resolution: fixed. The manifest description is neutral, and the metadata scan now covers Python, JSON, and Markdown files under `src\aeat` and `tests`.

## Verification Notes

- `uv run pytest src\aeat\adapters\outbound\aeat\sede\test_declarations.py::TestSubmittedFileObservation::test_modelo_130_redacted_submitted_file_matches_registry_calculation -q` passed.
- `uv run pytest src\aeat\adapters\outbound\aeat\sede\test_declarations.py -q` passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_registry_schema.py src\aeat\domain\calculations\registry\test_formula_runtime.py src\aeat\domain\deadlines\test_engine.py tests\fixtures\pdf_corpus\l3_synthetic\_generators\test_generator_shared.py -q` passed.
- `uv run ruff check` on the reviewed Python files passed.
- `uv run ty check src\aeat\adapters\outbound\aeat\sede\test_declarations.py` passed.
- `git diff --check` on the reviewed files reported only line-ending warnings.
- `uv run --no-sync vaultspec-core vault check all` failed on broad pre-existing vault structure/frontmatter/link issues and also reports the reviewed exec filename as a structure violation. The specific reviewed plan and exec frontmatter contain the required directory tag, feature tag, date, and quoted related wiki-links.

## Status

MEDIUM FINDING RESOLVED; LOW MODELO 111 SCOPE NOTE REMAINS FOR THE MODELO 111 OWNER
