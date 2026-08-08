---
tags:
  - '#exec'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:ea94789298374372285360149281f520b9f12314f39ebd8b3ef0e865ff3a21f6'
step_id: 'S07'
related:
  - "[[2026-08-08-m200-export-envelope-tag-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m200-export-envelope-tag with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-08-08-m200-export-envelope-tag-plan placeholders are machine-filled by
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
     The run the fichero-BOE parity and completeness gates for M200 and confirm they stay green after the restructuring and ## Scope

- `src/cadrumo/application/filing/tests/test_export_completeness_gate.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# run the fichero-BOE parity and completeness gates for M200 and confirm they stay green after the restructuring

## Scope

- `src/cadrumo/application/filing/tests/test_export_completeness_gate.py`

## Description

- Run the fichero-BOE completeness gate, the completeness-set gate, the
  fichero-BOE completeness parity gate, the fichero-BOE roundtrip and the export
  layout refusals together, which are the gates the export-structure rules name.
- Run the whole registry and filing test packages serially, so the restructured
  page-000 record is exercised by every consumer of the Modelo 200 layout rather
  than only by the assertions written for it.
- Run a whole-tree collection to confirm nothing imports a symbol this change moved.
- Triage every failure by owner before reading the result.

## Outcome

The five named gates pass. The wider run reports 8 failures out of 4315 selected
tests, and none is on this feature's surface: not one names the Modelo 200 page-000
record, the envelope footer, the draft-attribute width table, or any test authored
here. Every Modelo 200 export assertion passes.

Triaged by owner:

- Two decimal export-field failures fail while constructing a Modelo 303 field
  inside the test's own fixture, against a newly-required `decimals` declaration.
  The validator is a peer's; the fixture is stale against it. No dependency on any
  file this feature touched.
- One formula-parity failure reports two Modelo 303 rate constructs unowned by a
  construct with snapshot workflow surfaces. Peer Modelo 303 registry work.
- Two Modelo 390 mutation proofs fail with "the mutation target string was not
  found -- test is stale": they string-match Modelo 390 registry TOML a peer has
  since edited. Peer Modelo 390 work.
- Two loader cache-isolation failures come from a child process refusing the load
  outright: "registry directory changed during cache fingerprinting; retry after
  concurrent registry writes settle". That is the shared tree being written during
  a 21-minute run, not a defect in the tree.
- The revision-span gate reports Modelo 200, 303 and 390 revisions each spanning a
  published re-layout. It compares AEAT's design sheets against each other across
  whatever year span a revision claims, and its own module documentation states it
  does not compare a revision's layout to its design at all. Its Modelo 200 finding
  is a 75-to-77 record-set change between the 2024 and 2025 published sheets, and it
  cites design offsets. Nothing in it reads the registry declaration this feature
  changed, and it reports two modelos this feature never touched.

An earlier collection run in the same session reported 10 collection errors under
`entrypoints/cli`. Re-running after HEAD moved collected clean, and the collected
count had risen from 26540 to 26685 -- peers landing work mid-run. Reporting the
first reading as a result would have been wrong.

## Verification

<!-- Where the evidence is that something RAN, quote the instrument rather than
     summarising it: the invocation, then the runner's verbatim summary line.

         uv run --no-sync pytest <paths> -m integration -n 0
         15 passed in 10.35s

     The invocation shows the selection (marker expression and path scope); the
     summary line shows what that selection produced. A run that selected nothing
     exits zero and reads as green, so a paraphrase such as "the tests pass"
     discards exactly the part a reader needs. Quote, do not summarise. -->

The named export-structure gates:

    uv run --no-sync pytest src/cadrumo/application/filing/tests/test_export_completeness_gate.py src/cadrumo/application/filing/tests/test_export_completeness_sets.py src/cadrumo/application/filing/tests/test_fichero_boe_completeness_parity.py src/cadrumo/application/filing/tests/test_fichero_boe_export_roundtrip.py src/cadrumo/application/filing/tests/test_export_layout_refusals.py -n0 -q
    30 passed in 18.11s

The registry and filing packages in full, serially:

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests src/cadrumo/application/filing/tests -n0 -q
    8 failed, 4307 passed, 29 deselected, 2 warnings in 1261.76s (0:21:01)

Whole-tree collection:

    uv run --no-sync pytest --collect-only -q
    22698/26685 tests collected (3987 deselected) in 75.08s (0:01:15)

Lint, format and type checks on every file changed:

    uv run --no-sync ruff check <changed files>
    All checks passed!

    uv run --no-sync ty check <changed files>
    All checks passed!

## Notes

The eight failures listed above are peer-owned and were left untouched. Patching
them to green a closeout would have edited files belonging to active peer work.

The serial run is not a preference: parallel pytest on this host produces
loader-cache races and I/O failures that read as regressions, so `-n0` is what
makes the reading trustworthy.
