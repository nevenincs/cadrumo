---
tags:
  - '#audit'
  - '#runtime-verification'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:615b431070c018f3248d438aea06b1f2a302b52807de48a9a2fc71d29917fa26'
related: []
---

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

### L01-R01-F02 | high | runtime `materialize` builds single-revision modelo views that the whole-modelo `reviewed_against` validator rejects

Follow-up trace of F01's unproven boundary, using read-only source inspection, git history, and a read-only (`mode=ro`) SQLite query of the published generation. No product command or test was rerun.

The authority document is confirmed: `src/cadrumo/_data/registry/authority/authority.current.json` (format `cadrumo-authority-descriptor-v1`, logical generation `2bdbfabc…2c66`) selects `authority-06f66544…a2dd.sqlite3` (82059264 bytes). Both files are dated 2026-09-15 14:13:44 and were committed in `2aa0fec2d0` (14:23 +0200), after the last 038 source commit `427d431bd7` (07:10). Neither file has uncommitted changes. Runtime opens the descriptor through `bundled_indexed_authority()` → `IndexedRegistryAuthority` → `SQLiteAuthorityReader` (`src/cadrumo/domain/calculations/registry/authority.py:841-912`).

The published generation is complete for 038. It has a `modelo_directory/038` component whose `revisions` metadata lists `2024-desde-06` and `2025-y-siguientes`, plus one `modelo_revision` component for each. So the predecessor is not lost by publication or the temporal envelope.

The drop happens at runtime materialization. The call chain is `list_modelos` (`src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py:194`) → `registry_list_modelos` (`src/cadrumo/application/modelo/registry_discovery.py:98`) → operation-backed `list_modelos`/`iter_modelo_definitions` (`src/cadrumo/domain/calculations/registry/queries.py:865-884`). For each modelo, that code picks the latest revision and calls `ModeloDirectoryMetadata.materialize` (`src/cadrumo/domain/calculations/registry/temporal.py:101-106`), which constructs `ModeloDefinition(..., revisions={revision.id: revision})`. Constructing it runs `ModeloDefinition._validate_revisions` (`src/cadrumo/domain/calculations/registry/schema.py:1365-1386`), which requires `reviewed_against` to name a revision inside that same map. A single-revision view can never satisfy this when the revision was reviewed against its predecessor.

Introduction order from `git log -S`: the single-revision `materialize` arrived in `e1750fc549` (2026-09-14 13:42). The dangling-review check arrived in `dbf893a38f` (2026-09-14 19:29). The 038 `reviewed_against` data predates both (`6799c36830`, 2026-09-12). The check therefore conflicts with an existing runtime projection. The data did not change.

Blast radius: authored source holds about 50 revisions across about 35 modelos (for example 131, 184, 303, 390, 714) whose `reviewed_against` names another revision. `038` fails first only because iteration is sorted by modelo id. Other `materialize` call sites (`authority.py:749` selected-snapshot path, `queries.py:1060` query context, `entrypoints/tui/launcher.py:682`) share the construction and are expected to refuse the same revisions. That expectation is inferred from the code and was not exercised.

Unproven: whether any consumer besides `modelo list` actually fails at runtime (not executed), and whether the full compile/publish path still validates `reviewed_against` against the complete revision map (inferred from publication success, not traced).

## Recommendations

- For `L01-R01-F02`: the follow-on decision is which invariant owns `reviewed_against` integrity. One option is to validate it only at whole-modelo compile or publication and keep single-revision runtime views free of cross-revision references. The other is to have runtime views carry, or check against, the directory's full revision identity set. It needs an ADR or an amendment to the governing authority decision before remediation. The smallest evidence probe that follows is one execution of a selected-snapshot consumer (for example `aeat app modelo describe 131`) to confirm that the blast radius extends beyond `modelo list`.

- For `L01-R01-F01`: next evidence lane should establish which authority `aeat app modelo list` consumes (published generation versus source) and whether that artifact carries `038/2024-desde-06`. If the loader intentionally omits out-of-envelope predecessors, the follow-on decision is whether `reviewed_against` validation runs against the full authored revision set or the selected one; that choice belongs in an ADR, not here.
- Remediation is not authorized by this lane.
