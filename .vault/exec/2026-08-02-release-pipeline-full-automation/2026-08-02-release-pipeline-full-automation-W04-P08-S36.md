---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:efe8b2478852fc9609579aeaf3463d45734a14de3e68040bbb7a5501da598d60'
step_id: 'S36'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace release-pipeline-full-automation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S36 and 2026-08-02-release-pipeline-full-automation-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Record OP-12 as a named operator settings action deleting the orphaned pypi-data-official environment, which is a live Trusted Publishing trust anchor naming a workflow that no longer exists and therefore standing authority with no owner, and extend the read-only forge inventory probe to report any environment referencing an absent workflow so the orphan class is detectable rather than rediscovered, gate: uv run --no-sync pytest dev/release/tests -q -k environment_inventory passes with a case whose fixture environment names a workflow path absent from the tree and is reported as orphaned and ## Scope

- `dev/release/environment_inventory.py`
- `dev/release/tests/test_environment_inventory.py`
- `RELEASING.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Record OP-12 as a named operator settings action deleting the orphaned pypi-data-official environment, which is a live Trusted Publishing trust anchor naming a workflow that no longer exists and therefore standing authority with no owner, and extend the read-only forge inventory probe to report any environment referencing an absent workflow so the orphan class is detectable rather than rediscovered, gate: uv run --no-sync pytest dev/release/tests -q -k environment_inventory passes with a case whose fixture environment names a workflow path absent from the tree and is reported as orphaned

## Scope

- `dev/release/environment_inventory.py`
- `dev/release/tests/test_environment_inventory.py`
- `RELEASING.md`

## Description

Extended `dev/release/environment_inventory.py` with orphan detection: `environments_referenced_by_workflows(repo_root)` scans `.github/workflows/*.yml` for job-level `environment:` declarations (both the bare scalar form and the `{name, url}` mapping form), returning environment name → the live workflow paths that reference it. `EnvironmentRecord` gained a `referenced_by: tuple[str, ...] | None` field and an `is_orphaned` property, mirroring the existing readable/unreadable three-way distinction: `None` when the repo-tree scan wasn't performed, `True` only when the environment is confirmed to still exist on the forge AND no live workflow references it. `fetch_environments()` gained an optional `repo_root` parameter opting a caller into the scan; omitted, behaviour is byte-identical to before. Added `ORPHAN_CANDIDATE_ENVIRONMENTS = ("pypi-data-official",)` and `DEFAULT_INVENTORIED_ENVIRONMENTS` (OP-9's two plus every orphan candidate), and wired `main()` to default to the full set with `repo_root` supplied. `render_report()` now emits an `OP-12 OUTSTANDING - ORPHANED` line naming the delete-environment path when orphaned. Recorded OP-12 in RELEASING.md's Operator actions section (renamed from `(OP-9)` since it now covers two obligations), naming the GitHub-settings deletion step and separately naming the index-side PyPI Trusted Publisher registration check as an item no agent can perform or confirm from here.

## Outcome

Gate green: `uv run --no-sync pytest dev/release/tests -q -k environment_inventory` — 17 passed (8 pre-existing + 9 new). The named gate case (`test_fetch_environments_marks_an_unreferenced_environment_as_orphaned`) plants a fixture repo tree whose workflows reference `release`/`docs` but not `pypi-data-official`, confirms a real stub-gh-readable `pypi-data-official` payload, and asserts `is_orphaned is True` plus `OP-12 OUTSTANDING`/`ORPHANED` in the rendered report. Companion cases cover: a referenced environment reported not-orphaned; `is_orphaned` staying unknown (`None`) without a `repo_root` scan; `is_orphaned` never `True` for an unreadable environment; both the scalar and mapping `environment:` forms parsed; a malformed neighbour workflow file not blinding the scan to the rest; an empty/absent workflows directory returning cleanly. Sanity-checked `src/cadrumo/tests/test_release_config.py -q` (8 passed) unaffected by the RELEASING.md prose edit.

## Notes

No incidents. Orphan detection is deliberately scoped to what this repository can verify (no live workflow claims the environment); the external half — whether PyPI's own Trusted Publisher registration still names the retired workflow — is explicitly named as unverifiable from here, both in the module docstring and in RELEASING.md, per the ADR's own honesty framing (an index-account action outside the repository and the forge).
