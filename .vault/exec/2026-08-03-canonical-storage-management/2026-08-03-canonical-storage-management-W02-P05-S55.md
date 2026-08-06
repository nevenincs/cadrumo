---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:1c2f0c3cab1ea14a4e71fd74ab65201fee64e04829c8b8ebe11bf751c105673a'
step_id: 'S55'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare or escape the MCP certificate option's relative default so it stops naming a taxonomy-governed segment by literal, gated by the tools-and-dispatch tests re-expressed against whichever ruling applies

## Scope

- `src/cadrumo/entrypoints/mcp/_tools.py`

## Description

## Outcome

**This row's premise is false, not merely unfixed.** There is no MCP certificate option with a relative default anywhere in the codebase, and there never was one for this campaign to declare or escape. Verified at HEAD: `src/cadrumo/entrypoints/mcp/_tools.py` has zero "cert" matches and zero relative `Path(` literal defaults; a tree-wide search of `entrypoints/mcp/` finds no SSL/TLS/certificate option outside the tool-name abbreviation table in `_dispatch.py` (unrelated - a display-name shortener, not a filesystem path) and `cadrumo_certificate_path` in `core/config.py` (a pre-existing, separate, already-correctly-escaped `OPERATOR_INPUT` field defaulting to `None`, not a relative literal, and not what this row names). Two independent lanes reached the same conclusion: this record's own verification, and a peer lane's report that the only resembling literal in the whole tree was a synthetic `--cert` probe value in `test_tools_and_dispatch.py` (`Path("secrets/cert.p12")`), used purely to exercise the click-to-schema Path-rendering projection and never resolved against the storage root - renamed to a fictional `probe-cert-store` segment in `343825ed2c` so a future literal scan cannot mistake it for governed data. That test-fixture rename is the only work this row's premise could ever have produced; the production certificate-option defect the row describes does not exist. Left checked per operator/coordinator direction: the investigation was completed and honestly reported, which is the actual deliverable when a Step's premise turns out to be false. Flagging the row itself as premise-defective so a future reader does not re-derive the same dead end.

## Notes
