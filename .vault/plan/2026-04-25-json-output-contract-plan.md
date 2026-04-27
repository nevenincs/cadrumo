---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/plan/ location)
# Feature tag (replace json-output-contract with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#plan'
  - '#json-output-contract'
# ISO date format (e.g., 2026-02-06)
date: '2026-04-25'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-adr]]")
related:
  - "[[2026-04-25-json-output-contract-research]]"
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-04-24-aeat-cli-wireframe-reference]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `json-output-contract` `phase-1-through-phase-3` plan

Implement the foundational `--json` output contract for issue `#399` in a
way that is safe to land before sibling branches `#398` and `#393`, while
still leaving a complete, audited path for the later rebases that finish
the full command rollout.

## Proposed Changes

The work is split by the issue's mandated phasing:

- Phase 1 ships standalone foundation modules, tests, docs, env/config
  plumbing, and vault artifacts with no imports from sibling-owned code.
- Phase 2, after `#398` merges, replaces the temporary stderr-only exit helper
  path with the real `aeat.errors.ErrorEnvelope` integration and wires the
  root-level `--json` path across Kent-first non-workflow commands.
- Phase 3, after `#393` merges, adds the final workflow command bindings and
  their pipe-safety regressions.

The current execution pass targets Phase 1 completely and documents the
remaining Phase 2 and Phase 3 steps as explicit follow-on work.

## Tasks

### Phase 1

1. Create and publish the shared CLI foundation modules:
   `src/aeat/cli/_schemas.py`, `_exit_codes.py`, `_tty.py`,
   `_log_levels.py`, plus the public `aeat.cli` re-exports.
2. Extend `src/aeat/logging.py` with the record-level scrubber and shared
   scrub field list.
3. Update `src/aeat/config.py` and `env/.env.example` for `AEAT_LOG_LEVEL`.
4. Add the colocated unit coverage for registry behavior, exact exit-code
   mapping, subprocess-observed TTY behavior, log-level resolution, and
   rendered-output log scrubbing.
5. Write the user-facing docs that Phase 1 can truthfully support now:
   exit-code table, JSON contract foundations, and the Kent capability matrix.

### Phase 2

1. Rebase after `#398` merges and replace the plain stderr-only helper path
   with the real `aeat.errors.ErrorEnvelope` import and serialization.
2. Add the root-level `--json` context option callback and wire the success
   path across every Kent-first command except workflow `run` / `next`.
3. Register per-command output schemas and add canonical `jq`, `tee`, and
   `xargs` integration regressions.

### Phase 3

1. Rebase after `#393` merges.
2. Add the root-level `--json` wiring to `src/aeat/cli/workflow/run.py` and
   `src/aeat/cli/workflow/next.py`.
3. Add workflow-specific pipe-safety tests.

## Explicit Plan Review

Review outcome: approved for execution as a Phase 1-only implementation pass.

- `CLAUDE.md` / project mandates:
  the plan keeps new Python modules under `src/aeat/`, uses pytest,
  preserves public imports through `aeat.cli`, keeps boundaries strict,
  and avoids mocks/fakes as a shortcut.
- Issue scope:
  the plan covers every required Phase 1 deliverable from Step 3, plus the
  requested docs and vault artifacts.
- Iteration-7 reference alignment:
  the plan implements the shared transport primitives now and defers command
  bindings until the sibling dependencies exist.
- Trilingual contract:
  Phase 1 avoids inventing user-facing JSON message bodies beyond the minimal
  warnings list; any later human-facing payload fields remain subject to the
  trilingual emission rule in Phase 2.
- Sibling-branch boundaries:
  Phase 1 avoids `src/aeat/sede/`, `src/aeat/auth/_clave_movil.py`,
  `src/aeat/cli/workflow/run.py`, `src/aeat/cli/workflow/next.py`,
  and all `#398` registry/decorator files.
- Phasing check:
  every Phase 1 deliverable is implementable without importing code from
  `#239`, `#393`, or `#398`. The deferred work is explicit rather than implied.

## Parallelization

Phase 1 supports bounded parallelism:

- vault research can run in parallel with local codebase discovery
- documentation should use the required two-subagent workflow after the
  implementation surface is stable enough to document accurately
- mandatory code review should run after local verification and before the
  exec summary is finalized

Source edits themselves should stay mostly serial because the root logging
surface, config/env plumbing, and public CLI re-exports overlap.

## Verification

Phase 1 is complete when:

- the four new foundation modules exist and are re-exported from `aeat.cli`
- `src/aeat/logging.py` scrubs sensitive record fields before formatting
- the exact exit-code table is documented and regression-tested
- `AEAT_LOG_LEVEL` exists in config and `env/.env.example`
- the new unit suites pass and the broader quality gates are green:
  `just lint`, `just typecheck`, `just test`, `just hooks`
- the mandatory audit runs and records any remaining risks

Verification should prioritize transport behavior over line coverage:

- subprocess TTY tests should prove the helpers respond to piped stdio
- exit-code tests should assert the exact stable mapping
- log-scrubbing tests should inspect rendered output, not helper internals
- final gate runs should confirm the new modules integrate cleanly with the
  existing tree
