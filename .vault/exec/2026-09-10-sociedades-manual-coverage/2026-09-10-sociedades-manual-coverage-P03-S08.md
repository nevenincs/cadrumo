---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:bd0a8427251fd1fc9ae9c6dc51be6a13645934f324f9ef4576362ffd09947d82'
step_id: 'S08'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Replace Sociedades standing acquisition exceptions with catalogue-driven temporal coverage tests

## Scope

- `dev/corpus/tests/test_extraction_sidecar_freshness.py`

## Changes

- `M` `dev/corpus/tests/test_extraction_sidecar_freshness.py`
- `verify:` `uv run pytest dev/corpus/tests/test_extraction_sidecar_freshness.py -k "supported_tax_manual_matrix or manual_pdf_corpus_text_sidecars_exist or every_corpus_pdf_has_a_corpus_text_sidecar"` -> `pass`

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->
