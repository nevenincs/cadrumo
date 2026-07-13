---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S76'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
  - "[[2026-07-13-cadrumo-product-rename-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S76 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Audit remaining `aeat` tokens and classify each as the sole CLI, authority, historical evidence, immutable corpus, or defect and ## Scope

- `repository rename residue report` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Audit remaining `aeat` tokens and classify each as the sole CLI, authority, historical evidence, immutable corpus, or defect

## Scope

- `repository rename residue report`

## Description

- Inventory retained `aeat`/`Aeat`/`AEAT` tokens across `src/cadrumo`, `packaging`, `dev`, and `.github`.
- Classify each cluster by referent against the accepted executable ADR: authority-correct, intentional owner-gated, or genuine defect.
- Re-verify the `W06.P14.S77` compatibility-absence gate expectations at HEAD.
- Persist the full classification in the vault audit `2026-07-13-cadrumo-product-rename-audit`.

## Outcome

The residue report is recorded in `2026-07-13-cadrumo-product-rename-audit`. Class-a
authority uses (adapter tree, registry taxonomy, official corpus, 49 `AEAT_*`
authority env vars, `aeat_live` marker, the `aeat` executable token, AEAT prose) are
correct and preserved. Class-b intentional owner-gated: 36 `b"aeat.*.v1"` crypto
domain-separation labels (unchanged; rekey only under operator sign-off) and the
`AeatError` base class + 645 references (follow-up `F-ERR-01`, own reconciliation).
Genuine defects: D-CI-01 (`ci.yml` invokes nonexistent `cadrumo` command — `S58`
reopened), D-PKG-01/02 (`smoke_docker.py`, `smoke_split_install.py` invoke a
nonexistent `cadrumo` script — `S39`/`S40` correctly open), D-PKG-03/04 (the two
tests asserting those defects), D-DOC-01/02 (companion READMEs and mcpb build
docstring cite `cadrumo app ...`), D-ENV-01 (stale `AEAT_ACTIVE_BUCKET` docstring),
and review cluster R-ARGV (tests set `argv[0] = "cadrumo"`). The `S77` gate
re-verified PASS against the superseding executable ADR.

## Notes

Grounding: the deliverable of this Step is the audit document
`2026-07-13-cadrumo-product-rename-audit` authored in this bookkeeping pass. The
step is closed on that report. The three hard executable defects (D-CI-01,
D-PKG-01, D-PKG-02) are left tracked and open on their owning Steps (`S58`, `S39`,
`S40`) rather than fixed here, because this pass is bookkeeping and residue
classification, not remediation. No production code was modified.

## Bookkeeping grounding (2026-07-13)

This pass also closed the plan checkboxes below, each grounded in the landing commit
that completed its primary scope and each backed by a pre-existing execution record.
`step` -> `commit` -> primary file:

- `S37` -> `4ceb1baad2` -> `dev/packaging/smoke_core.py` (installed `aeat` script)
- `S38` -> `4ceb1baad2` -> `dev/packaging/smoke_extras.py` (installed `aeat` script)
- `S43` -> `81e101b2b6` -> `src/cadrumo/entrypoints/mcp/_server.py` (argv uses `PRODUCT_IDENTITY.cli_executable` = `aeat`; server id `cadrumo`)
- `S45` -> `81e101b2b6` -> `src/cadrumo/entrypoints/mcp/_prompts.py` (`cadrumo://` scheme)
- `S48` -> `1c02648450` -> `src/cadrumo/agent/_workspace.py` (plugin `cadrumo`, pin `cadrumo[agent]`, launcher `cadrumo-mcp`)
- `S49` -> `1c02648450` -> `src/cadrumo/agent/tests`
- `S50` -> `3d7636380f` -> `packaging/marketplace` (regenerated manifest)
- `S51` -> `3d7636380f` -> marketplace strict validation evidence
- `S52` -> `3c72d89745` -> `packaging/mcpb/manifest.json`
- `S53` -> `301cd487d7` -> `packaging/mcpb/build.py` (emits `cadrumo.mcpb`; D-DOC-02 docstring follow-up)
- `S54` -> `301cd487d7` -> `packaging/mcpb/tests/test_build.py`
- `S57` -> `76b0e3b694` -> `.github/workflows/packaging-smoke.yml`
- `S62`-`S67` -> `38894cae07` (Cadrumo prose casing) atop the locale-phase landings `6cd7c88722`/`4f730953bb`/`cdaff8f301`/`3a5ac58ba0`/`fcd7d718ca` -> `src/cadrumo/locales/{en,es,ca,hu}.yml` and help authorities. Verified at HEAD: zero all-caps `CADRUMO` used as a product name in prose; every all-caps occurrence is a `CADRUMO_*` env var.
- `S78` -> `cef5f45fa1` -> focused Cadrumo feature-gate (64 passing real-behavior tests per the S78 record).

Deliberately left unchecked: `S25` (contested; the S25 record's own outcome states
formal review did not accept live `aeat --help`, and the help acceptance was
reopened), `S39`/`S40` (defects D-PKG-01/02), `S58` (reopened, defect D-CI-01),
`S61` (publication gate, blocked by design), `S05`, `S86`, `S68`-`S75` (docs wave;
landed per the team lead but carry no execution records and were not verified in this
pass), `S79`/`S80` (gate runs, no record), and `S81`-`S85` (formal review and
closure).
