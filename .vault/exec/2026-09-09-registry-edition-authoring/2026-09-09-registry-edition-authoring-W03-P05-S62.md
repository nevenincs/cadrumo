---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:0848e5d38f60142591e145fbf7a3819402311e4de3f625e10d1ac40a678f4e07'
step_id: 'S62'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [M | opus-medium] Implement the amended materialiser contract before the live pilot: (1) the round-trip gate's order assertion compares against the full copy rearranged into the merge order (inherited in predecessor order, superseders in place, new rows appended), with content still element-wise; (2) a row may state source references in addition to the edition's casilla_source_refs, materialising as default followed by additions that inherit with the row, while a full source_refs still replaces (name the additions key canonically); (3) continuidad_origin and continuidad_evidence are never inherited — an inherited row materialises with both unset; (4) the delta-minimality screen judges stated rows only, via a statement-origin marker, not inherited ones. Then re-run the migration script's 303 dry run. Proof: all five 303 successor editions migrate exactly in the dry run, the round-trip gate passes on them, delta-minimality is clean for 303, and the unmigrated corpus is byte-identical.

## Scope

- `src/cadrumo/domain/calculations/registry`

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
