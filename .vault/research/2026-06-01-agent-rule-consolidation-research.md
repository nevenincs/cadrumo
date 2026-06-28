---
tags:
  - '#research'
  - '#agent-rule-consolidation'
date: '2026-06-01'
modified: '2026-06-01'
related: []
---



# `agent-rule-consolidation` research: `Worktree hygiene, memory triage, and rule-system audit`

The shared `chore/*` worktree hosts many concurrent campaign agents that leave
residual scratch, accumulate per-session auto-memory notes, and let project
rules drift out of sync with the live codebase. This research inventories three
surfaces — untracked worktree clutter, the per-project agent memory store, and
the installed custom rule set — to decide what to sweep, what to drain into the
rule system, and what rule text has gone stale.

## Findings

### Worktree clutter

The working tree carries heavy in-flight campaign WIP (modified CLI test files,
a new `test_casilla_keying_convention.py`, edited `.vault` plans, a deleted
`scripts/gen_api_stubs.py`) that is peer work and out of scope. The untracked
*root* surface is ephemeral agent scratch the existing `.gitignore`
"Top-level scratch outputs" block does not match: commit-message temps
(`.msg`, `.commit-msg-*.tmp`), multi-hundred-KB capture dumps
(`dom_*.txt`, `fails.txt`, `apex.txt`, `campaign_run.txt`), trace/check helpers
(`trace_imports*.py`, `check_*.py/ps1`, `test_fix.py`), ad-hoc runners
(`run_test*.sh`, `_coder2_tmp_run.ps1`, `_writer.py`), and an `api.bak/` copy of
generated `.rst` docs. `AGENTS.md` and `GEMINI.md` are vaultspec **provider
outputs** (same `<vaultspec type="config">` header as `CLAUDE.md`), regenerated
by sync — not junk and not authorship surfaces.

### Agent memory store

The per-project memory store holds 38 notes plus an 8 KB `MEMORY.md` index that
loads every session. Triage classifies them: ~18 are fully **covered** by an
existing rule (the four destructive-git notes by `aeat-git-worktree-safety`; the
metastate/dev-metadata/retire notes by `aeat-source-hygiene`; the oracle/noqa
notes by `aeat-quality-gates` and `no-tautological-calculation-tests`); ~4 are
**transient** project/environment state (`work_domain_map`,
`semantic_cluster_hardening_autonomous_drive`, `bash_lacks_pgrep_*`,
`update_vaultspec_in_locked_venv`); the remainder carry durable
shared-worktree-orchestration and audit-discipline lessons that exist **only** in
memory and belong in the rule system.

### Rule-system drift and bloat

Custom rules total ~387 source lines across 17 files. Truthfulness rot found and
confirmed against the live tree:

- `core-struct-docstring-links` formerly hard-listed "the spine of 9" structs;
  the gate's `CORE_STRUCTS` map now enforces 28. A peer had already corrected the
  **source** to point at the map as authoritative, but the stale "53%/26%
  baseline scan" frozen statistic remains.
- `aeat-campaign-close-honesty-review` embeds a specific campaign's audit path
  (`.vault/audit/2026-05-27-modelo-130-…`) and frozen "~30%" / "~14-item"
  statistics that will rot.

Bloat: `aeat-git-worktree-safety` is 101 lines (the forbidden/allowed command
lists are load-bearing and must stay; the repeated "ABSOLUTE PROHIBITION"
narrative and CONSEQUENCES prose can tighten). `aeat-swarm-audit-cadence` (22
dense paragraphs) and `aeat-rag-discovery` (26) are operating-manual-length.

A meta-finding observed live: a peer hand-edited the **generated**
`.claude/rules/` copy of a rule rather than the `.vaultspec/rules/rules/project/`
source — a forbidden edit that `vaultspec-core sync` silently reverts. Rule
corrections MUST land on the source and propagate via sync.
