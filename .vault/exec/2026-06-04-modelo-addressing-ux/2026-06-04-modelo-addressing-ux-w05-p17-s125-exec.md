---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S125'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W05.P17.S125` Documentation raw-ID coverage

Step scope: `docs`.

## Description

- Ran exact raw-ID workflow leakage scan across Markdown narrative docs.
- Rebuilt the edited how-to index after removing stale raw-ID framing.
- Re-ran docs conformance and generated reference drift checks.
- Ran semantic `vaultspec-rag` closure searches for operator-facing raw-ID copy/paste workflows.

## Outcome

Narrative docs exact scan returned no matches in the targeted user-facing pages:

- `rg -n "work_unit_id|calculation_revision_id|<work-unit-id>|<calculation-revision-id>|copy/paste|copy and paste|copy the|paste the|work unit ID|calculation revision ID" docs/tutorials/index.md docs/getting-started.md docs/how-to/quickstart.md docs/how-to/modelo-303.md docs/how-to/modelo-390.md docs/how-to/reconcile.md docs/how-to/filing-spine.md`
  returned no matches.

Generated CLI reference exact scan returned expected exact-ID parameter entries in
`docs/cli/app.rst`; these mirror live command signatures and are retained because raw
IDs remain advanced exact-addressing escape hatches.

Docs conformance passed:

- `.venv\Scripts\python.exe -m pytest -m docs src/aeat/entrypoints/cli/test_educational_docs_conformance.py src/aeat/entrypoints/cli/test_doc_reference_drift.py src/aeat/entrypoints/cli/test_doc_reference_conformance.py`
  passed `37` tests.

Generated CLI reference regeneration completed:

- `.venv\Scripts\python.exe -c "from pathlib import Path; from aeat.entrypoints.cli._doc_reference import generate_cli_reference_in_subprocess; result = generate_cli_reference_in_subprocess(Path('docs')); print('generated', len(result)); print('\n'.join(sorted(result)))"`
  regenerated `cli/app.rst`, `cli/config.rst`, and `cli/index.rst`.
- `git diff -- docs/cli/app.rst docs/cli/config.rst docs/cli/index.rst` returned no
  diff after regeneration.

Semantic RAG closure searches in `W05.P17.S120` found expected
internal/test/exact-ID hits and the desired tutorial wording that the workflow
completes without copying raw internal IDs.
