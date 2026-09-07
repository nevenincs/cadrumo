---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:0eac0a988dce05857bb7907d55e99ad8e4ce7832f5f161fc0dac7f963a50280b'
step_id: 'S86'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Sweep the shipped tree for the read-never-written shape the secure-store gate structurally cannot see, since a file-backed artefact is not a repository and the output-language hint slipped past it: pair same-module functions across seven verb oppositions and report where production uses one side only. Five pairs, four already carrying matching evidence in this ledger and the fifth not an exact finding at all, so the sweep found no unrecorded debt and no gate is warranted -- a fail-closed check over that population could only report symbols already adjudicated.

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` unused 1038, exact 409, unchanged -- this step adjudicates and
  decides against a gate, it moves no symbols
- `verify:` module ratchet, secure-store gate and docstring ratchet exit 0;
  duplication 10 / 0.05%; dead code 0
- `verify:` symbol ratchet exits 1 on the same two peer lines
- `verify:` ledger validated -- 122 clusters, no double classification

## Notes

The previous step closed a read-never-written pair the secure-store gate cannot
reach, so this one asked how many more the tree holds. Five, and four are
already in this ledger with evidence matching what the sweep independently
concluded -- the mnemonic decoder in particular, where the sweep's own reading
(the phrase is handed on as an opaque secret and never turned back into
entropy) is the recorded rationale almost word for word. The fifth, `load_trace`,
is not an exact finding: traces are written by `run_context` and read by a human
outside the product.

No unrecorded debt, and that is the useful result rather than a disappointing
one. An independently derived detector rediscovering only adjudicated symbols is
evidence the shape is covered.

No gate was added, deliberately. A fail-closed check over this population could
only ever report symbols that already carry a decision, and a check that cannot
change state is not a signal -- it is a second place for the same facts to
drift.

The detector's first run was almost entirely false positives and the fix was one
this campaign has already made once: excluding the DEFINING module from the call
scan. A same-module caller is a real caller, and `read_registry_identity_stamp`
and `save_run` were both reached from inside their own file. Handing a function
to a collaborator counts too -- `read_draft=read_extraction_draft` is a use no
call-node scan sees. Membership changed almost completely between runs while the
count moved six to five, which is the signal to distrust: diff the members, not
the number.
