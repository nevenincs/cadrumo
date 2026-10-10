---
tags:
  - '#exec'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-10'
body_schema: 'body-v2'
body_hash: 'sha256:61da75708339a17ec813d0ca4136d3a2521b1aeea9a6715dab4cd39f32698691'
related:
  - "[[2026-10-10-mcp-parity-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `mcp-parity` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S10` `M` `src/cadrumo_harness/_data/agent/README.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/personas/cadrumo-classifier.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/personas/cadrumo-coordinator.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/personas/cadrumo-ledger-groomer.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/personas/cadrumo-modelo-preparer.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/personas/cadrumo-onboarding.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/personas/cadrumo-reconciler.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/personas/cadrumo-verifier.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/rules/cadrumo-operator-lifecycle-ordering.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/rules/cadrumo-operator-operating-rules.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/rules/cadrumo-operator-orientation-routing.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/rules/cadrumo-operator-safety-handoff.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-alta-contribuyente/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-exportar-declaracion/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-llevar-libro/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-100/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-111/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-115/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-130/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-131/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-180/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-190/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-193/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-200/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-202/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-303/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-309/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-322/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-349/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-353/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-369/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-390/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-rectificar-declaracion/SKILL.md`
- `S10` `verify:` `pytest dev/agent_eval/tests/test_rule_surface_conformance.py -n0 -m "unit or integration"` -> `pass`
- `S10` `verify:` `pytest src/cadrumo_harness/tests/test_skill_applies_when.py src/cadrumo_harness/tests/test_harness_data_ships.py -n0 -m "unit or integration"` -> `pass`
- `S10` `by:` `vaultspec-standard-executor`
