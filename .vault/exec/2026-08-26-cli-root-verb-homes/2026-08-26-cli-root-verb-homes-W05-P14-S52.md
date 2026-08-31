---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:51453a734be5928bbc68c9eb390192fb8e61db81cd98717b1e28dae8bb9de3d0'
step_id: 'S52'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Sweep the callers the earlier `reconcile file` to `import` rename left behind: 22 test invocations, six prose sites, four harness documents and the acceptance-wall catalogue

## Scope

- `src/cadrumo/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_reconcile_verb.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_work_natural_key.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_reconcile_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_payloads_modelo_reconcile.py`
- `M` `src/cadrumo/application/live/justificante.py`
- `M` `src/cadrumo/tests/acceptance_wall_catalogue.py`
- `M` `src/cadrumo-harness/src/cadrumo_harness/_data/agent/personas/cadrumo-reconciler.md`
- `M` `src/cadrumo-harness/src/cadrumo_harness/_data/agent/rules/cadrumo-operator-lifecycle-ordering.md`
- `M` `src/cadrumo-harness/src/cadrumo_harness/_data/agent/rules/cadrumo-operator-orientation-routing.md`
- `M` `src/cadrumo-harness/src/cadrumo_harness/_data/agent/skills/cadrumo-reconciliar/SKILL.md`
- `verify:` `pytest test_modelo_reconcile_verb.py -m integration` -> `19 failed -> 2 failed, both peer-owned registry coverage`

## Notes

Surfaced while re-running the reconcile suite after S51: nineteen tests failed
with `No such command 'file'`. The verb had been renamed to `import` earlier in
this campaign under the `--file` standard, and the callers were never swept.

The same lesson as S43, and it cost a second reproduction to learn properly. The
first pass caught six single-line invocations by grepping `"reconcile", "file"`
and fixed nineteen failures down to fifteen -- because fifteen more invocations
were multi-line argv lists where `"reconcile",` and `"file",` sit on separate
lines and no single-line pattern can see them. They were flipped by matching the
line whose predecessor is `"reconcile",`, each asserted.

Four harness documents under `src/cadrumo-harness/` cited the dead verb. The CLI
contract names that surface explicitly: a citation to a renamed verb hands the
agent an instruction it cannot recover from.

One further defect, not a rename residue: `test_reconcile_list_empty_is_instructive`
asserted an English string while the CLI resolved Spanish, so it could never
pass. A test asserting localised prose must pin `--language`; it now does.

Two failures remain and are NOT this rename. `m190` and `m390` declaration
reconciliation report `snapshot_unavailable`, which is registry coverage, and
three `test_modelo_work_natural_key` failures are a peer-added M111 profile
readiness requirement ("Is a colegio concertado").
