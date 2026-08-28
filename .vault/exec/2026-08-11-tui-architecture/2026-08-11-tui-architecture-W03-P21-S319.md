---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:39c9ee80b8fe1bb64bf5cd078111a7c1060002c20254e6ffa5e08c562cd78b75'
step_id: 'S319'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Apply the modelo 347 declaration floor to the RESOLVER-BUILT contraparte rows, which today are emitted unfiltered: `_build_contraparte_clave_rows` groups invoices and emits a row for every country-party-clave combination with no threshold test, so a counterparty whose total operations fall below the RD 1065/2007 art. 31 floor is declared anyway. This is an OVER-declaration live since the clave row family shipped, affecting claves A, B, F and G right now, and it is the direction the codebase does not watch -- the apparatus is built against under-declaration, so an over-declaring path produces valid output, no refusal and no signal. The floor is NOT absent from the codebase, which is why this was easy to miss: `validate_m347_threshold` already refuses operator-supplied rows on the manual detail-row input path, and the summary totals binding applies the floor to its own family; neither reaches the rows the invoice resolver builds. Route the resolver-built rows through the ONE canonical comparison in the m347 threshold module rather than writing a third copy -- that module's own docstring records that the comparison was previously written out separately in each family, byte-identical in two, so mutating one left the other green. Preserve its strict `>` semantics: a counterparty landing exactly on the figure is not declarable. Prove with a grounded case that a below-floor counterparty produces NO row through the real resolver, that an exactly-on-floor counterparty produces none either, and that an above-floor one still does

## Scope

- `the invoice source resolver contraparte row builder`
- `the canonical m347 threshold module as the single comparison home`
- `and a real-resolver threshold proof`

## Changes

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
