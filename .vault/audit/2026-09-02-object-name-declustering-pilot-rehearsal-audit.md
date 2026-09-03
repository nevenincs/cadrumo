---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:3e539aa4950cc10e4401b88c07f167fc103de135d8d6132d80efc03df0f22d85'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---



# `object-name-declustering` audit: `pilot rehearsal`

## Scope

The no-argument `just fix-object-names` contract was exercised against the reviewed leaf operation `rename-result-disposition-fragment-generator`. The live repository was treated as read-only; transformation and gates ran only below `C:\Users\hello\AppData\Local\Temp\cadrumo-object-name-k9fhovd_\repository`.

## Findings

### pilot-rehearsal | low | reviewed leaf component rehearsed successfully

The component ID was `sha256:571f12c12b655bd3325dd205c28ea87ddcfafd5037b93b834e29a34269d971c8`. It contained one operation, one existing definition path, zero direct importers, zero boundary crossings, zero dynamic references, and zero generated artifacts. The manifest digest was `sha256:4efbcba8a1608eb10a1e1b3780b03ac7c54ff9201ac83a45440f55b450cf362e`.

The exact changed-path set was `dev/registry/generate_result_disposition_fragments.py` and `dev/registry/result_disposition_fragment_generator.py`, with changed-path digest `sha256:19283d0247685ae1819616e8975ccdfa31625afa57611521636b894db2d244f1`. The source byte `sha256:4eed2284f884c35c18242e230e88f45b350f792bccba10ac888741657414c6ad` moved unchanged to the target in the disposable tree. The live source remained present, the live target remained absent, and the receipt reported `source_tree_unchanged: true`.

The enforced object-name count moved from 788 to 787 in the disposable tree. Finding `sha256:185e22d79ce6fa25f26b4d2086037944c305aa0b206078537c8fb89484b0f026` was resolved there; no finding IDs or signatures were introduced. The finding remains in the live tree because this step did not authorize or execute replay.

Both focused gates passed: the renamed generator module completed with exit code 0, and Ruff completed with exit code 0. The immutable receipt ID was `sha256:90a22a8761d23dee40568aefe9a97b34307116b0ec7295a11b1f626e0e74383c`; its evidence digest was `sha256:f59a05ffdc3390ab5bc4edc5cc091931ec28f13df14d9c59a4c1dcd9053f83d4` and its selected-path baseline digest was `sha256:94191fb87eabaf9f6e9d207f00ad3c8134ca8f429f52576d3019b4665e5e7209`.

## Recommendations

Retain the rehearsal root and receipt evidence for review. Any later live rename must use explicit apply mode with this exact receipt identity and must independently pass replay preflight; this audit does not authorize application.
