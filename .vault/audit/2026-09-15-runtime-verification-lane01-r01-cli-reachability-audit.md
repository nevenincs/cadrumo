---
tags:
  - '#audit'
  - '#runtime-verification'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:cc64eb7cf4dfb11ba9c207984d39774ea7d0814653c66e71a08e3b88bdb7cc7a'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace runtime-verification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `runtime-verification` audit: `CLI reachability evidence`

## Scope

Session `lane01-r01-cli-reachability`, evidence only, no remediation authorized. Worktree `Y:/code/cadrumo-worktrees/main`, branch `main`, dirty tree left untouched; the modelo 038 registry subtree had no uncommitted changes (last commit touching it: `427d431bd7`, 2026-09-15 07:10 +0200). Execution date 2026-09-15, Windows 11, PowerShell. Coordinator ran all probes; no subagent was dispatched.

Question: does the CLI launch, is `aeat app modelo bindings` reachable, and does one existing registry-backed listing test pass.

Signal: FAILED.

Command ledger (Probe ID, Command, Owner, State, Exit, Evidence, Claim):

- `L01-R01-P01` | `uv run --no-sync aeat --help` | coordinator | finished | 0 | 4.3 s; Spanish root help rendered listing exactly the `config` and `app` roots, start/flow/recovery/diagnostic sections, no traceback | CLI launches: PROVEN.
- `L01-R01-P02` | `uv run --no-sync aeat app modelo bindings --help` | coordinator | finished | 0 | 4.6 s; `Uso: aeat app modelo bindings [OPTIONS] COMMAND [ARGS]...` with subcommands `list` and `resolve` | bindings group registered and reachable at help level: PROVEN.
- `L01-R01-P03` | `uv run --no-sync pytest -o addopts= -n 0 --strict-config --strict-markers --capture=sys --tb=short -ra -q src/cadrumo/entrypoints/cli/tests/test_cli_startup_smoke.py::test_app_modelo_list_starts_without_unlocking_active_profile` | coordinator | finished | 1 | `1 failed in 30.70s` (54.6 s wall); assertion at test line 87, `result.returncode == 0` got 1; run log under `.logs/test-runs/2026-09-15/20260915T143341.060879Z-pytest-46120-e3504afd` | registry-backed listing succeeds: FAILED.

Each probe ran once. No additional product or test checks ran. Post-failure work was limited to read-only source and tree inspection to name the refusing declaration.

## Findings

### L01-R01-F01 | high | `aeat app modelo list` refuses with a registry validation error for modelo 038

The subprocess launched by the smoke test (`aeat app modelo list` under an active profile without secret) exited 1 with no traceback and the message: `Error. revision '2025-y-siguientes' has dangling review reference reviewed_against='2024-desde-06'; declared revisions are ['2025-y-siguientes']`. The message is raised by `ModeloDefinition._validate_revisions` in `src/cadrumo/domain/calculations/registry/schema.py` (around line 1376), which rejects any `reviewed_against` not present in the modelo's loaded revision map. The authored source `src/cadrumo/_data/registry/aeat/modelos/038/revisions/2025-y-siguientes/revision.toml` declares both `predecessor = "2024-desde-06"` and `reviewed_against = "2024-desde-06"`. The predecessor directory `revisions/2024-desde-06/` exists on disk with a `revision.toml` (`valid_from = 2024-06-01`) and five declaration families. Therefore the loaded `ModeloDefinition` that reached validation contained only `2025-y-siguientes` even though the predecessor is authored.

Consequence: one invalid modelo aborts the whole listing, so no registry rows render and the startup smoke contract fails. The CLI itself launches (P01) and command registration is intact (P02); the defect is in registry loading or validation at list time, not in startup imports.

Unproven: which boundary drops `2024-desde-06` before validation (temporal envelope or edition selection filtering out the predecessor, the published authority generation lacking it, or a source-to-definition hydration defect); whether other modelos fail the same way; whether `aeat app modelo bindings list` also fails, since P02 only proves help-level reachability.

## Recommendations

- For `L01-R01-F01`: next evidence lane should establish which authority `aeat app modelo list` consumes (published generation versus source) and whether that artifact carries `038/2024-desde-06`. If the loader intentionally omits out-of-envelope predecessors, the follow-on decision is whether `reviewed_against` validation runs against the full authored revision set or the selected one; that choice belongs in an ADR, not here.
- Remediation is not authorized by this lane.
