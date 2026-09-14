---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:08e3b622b36ce0c07407d4137f0b9f9fb6cdaa6cb0c69977c6c05ffe2a34c952'
step_id: 'S01'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Introduce the explicit source set and expose profile-source selection through pipeline/cli.py; thread captured schema through compilation, validation, fingerprints and memo identities without ambient fallback

## Scope

- `dev/registry`

## Changes

- `M` `dev/registry/compiler/authority.py`
- `M` `dev/registry/pipeline/cli.py`
- `M` `dev/registry/pipeline/authority_publication.py`
- `M` `dev/registry/tests/test_authority_enrollment.py`
- `verify:` `checkpoint A focused source/enrollment and component selection` -> `pass`

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
