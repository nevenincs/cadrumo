---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:00e0a77990a8ce55bfee2e3269c0d7f0e3543f3aaf0c94ad6146e6b7aa194c70'
step_id: 'S55'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S55 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Declare or escape the MCP certificate option's relative default so it stops naming a taxonomy-governed segment by literal, gated by the tools-and-dispatch tests re-expressed against whichever ruling applies and ## Scope

- `src/cadrumo/entrypoints/mcp/_tools.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Declare or escape the MCP certificate option's relative default so it stops naming a taxonomy-governed segment by literal, gated by the tools-and-dispatch tests re-expressed against whichever ruling applies

## Scope

- `src/cadrumo/entrypoints/mcp/_tools.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

**This row's premise is false, not merely unfixed.** There is no MCP certificate option with a relative default anywhere in the codebase, and there never was one for this campaign to declare or escape. Verified at HEAD: `src/cadrumo/entrypoints/mcp/_tools.py` has zero "cert" matches and zero relative `Path(` literal defaults; a tree-wide search of `entrypoints/mcp/` finds no SSL/TLS/certificate option outside the tool-name abbreviation table in `_dispatch.py` (unrelated - a display-name shortener, not a filesystem path) and `cadrumo_certificate_path` in `core/config.py` (a pre-existing, separate, already-correctly-escaped `OPERATOR_INPUT` field defaulting to `None`, not a relative literal, and not what this row names). Two independent lanes reached the same conclusion: this record's own verification, and a peer lane's report that the only resembling literal in the whole tree was a synthetic `--cert` probe value in `test_tools_and_dispatch.py` (`Path("secrets/cert.p12")`), used purely to exercise the click-to-schema Path-rendering projection and never resolved against the storage root - renamed to a fictional `probe-cert-store` segment in `343825ed2c` so a future literal scan cannot mistake it for governed data. That test-fixture rename is the only work this row's premise could ever have produced; the production certificate-option defect the row describes does not exist. Left checked per operator/coordinator direction: the investigation was completed and honestly reported, which is the actual deliverable when a Step's premise turns out to be false. Flagging the row itself as premise-defective so a future reader does not re-derive the same dead end.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
