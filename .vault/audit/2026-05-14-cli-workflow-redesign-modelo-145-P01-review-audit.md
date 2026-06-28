---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]'
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-adr]]'
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-research]]'
  - '[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-p01-s01-s06-exec]]'
---



# `cli-workflow-redesign` Code Review


MODELO-145-P01-001 | MEDIUM | Pin ADR-critical non-filing AEAT source facts

The P01 source catalogue test verified local checksum and byte integrity but
did not assert the AEAT facts that authorize the narrowed Modelo 145 reopening:
no presentation or processing before AEAT, payer-side processing, and no
electronic procedures. Add source-content assertions against the local AEAT
corpus files so a wrong-but-checksummed source cannot satisfy the P01 gate.

Resolution: fixed in `test_modelo_145_aeat_sources_pin_non_filing_scope`.

MODELO-145-P01-002 | MEDIUM | Pin Modelo 145 record-design identity

The record-design manifest test compared catalogue and manifest URL, byte
count, and hash, but did not assert the manifest identity or the official
record-design marker. Add assertions for the Modelo 145 manifest identity and
the `<T145010>` marker extracted from the official record-design PDF.

Resolution: fixed in `test_modelo_145_record_design_source_matches_manifest`
and `test_modelo_145_record_design_extracts_official_model_marker`.

Follow-up review: no blocker, high, or medium issues remain in the P01 review
scope. The reviewer re-checked that P01 introduces no `registry/aeat/modelos/145.toml`,
filing, deadline, live, portal, fake, stub, mock, or scaffold surface.
