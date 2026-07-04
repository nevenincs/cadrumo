---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S23'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# OPERATOR-VISIBLE: align the work calculate verb (G3, the canonical aggregation-engine entry) name to the reconciled one-verb story per aeat-cli-pull-and-file-standard, as one atomic commit

## Scope

- `author through the locale CLI (cli.app.modelo.work.calculate_help) and sweep the runtime write-policy allowlist`
- `error-registry default_suggestion`
- `cross-period next_action builders`
- `curated operator help`
- `and envelope command= identifiers`
- `regen docs-scaffold + locale scaffold in the same commit`
- `collect-only clean and the two conformance gates green before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/entrypoints/cli/_modelo_work_calculate_cli.py`
- `src/aeat/application/storage_write_policy.py`
- `src/aeat/core/errors/_registry.py`
- `src/aeat/application/operator_surface/_help.py`

## Description

- Re-read the current `work calculate` CLI implementation after the command split and confirm it remains the canonical aggregation-engine entrypoint.
- Confirm the live command is still `aeat app modelo work calculate`, with envelope command `modelo.work.calculate` and text operation `modelo.work.calculate`.
- Confirm the runtime write-policy allowlist, error-registry default suggestions, cross-period next actions, operator help, and generated docs all still point at `work calculate`.
- Treat the current name as already aligned with the reconciled one-verb story: unlike the retired `bindings preview` and split `calc pull --compute` surfaces, `work calculate` is already the value-bearing calculation verb and does not need a rename.
- Re-run focused S23 evidence at HEAD.

## Outcome

- S23 is evidence-complete at HEAD without a code change. The command name and envelope identifier already express the canonical calculation operation, and no stale `preview` or Sheets-pull wording was found on the `work calculate` operator surface.
- Focused verification passed:
  - `uv run --no-sync vaultspec-rag search "work calculate verb one learnable verb story binding vocabulary" --type code --port 8766 --max-results 12 --timeout 30`
  - `uv run --no-sync aeat app modelo work calculate --help`
  - `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py` (`140 passed`)
- The documented-command conformance gate was rerun and failed on unrelated `aeat app agent` citations in `docs/HARNESS-USERDOCS-KICKOFF-BRIEF.md` and `README.md`; it did not report a `work calculate` citation failure.
- Focused collect-only over the selected CLI surfaces was attempted, but the current pytest marker configuration deselected the selected tests and returned `no tests collected`; no collection error specific to `work calculate` was observed.

## Notes

- No plan step check was run in this pass. The plan file currently has non-authored WIP that only removes the template link-rule comment block, so mutating the checkbox would violate the shared-worktree abort-on-WIP rule.
- No runtime, locale, docs-scaffold, or generated schema files were edited for S23 because the live surface is already aligned.
