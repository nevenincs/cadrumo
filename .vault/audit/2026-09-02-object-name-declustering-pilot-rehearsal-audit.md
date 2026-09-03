---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:f1b1b336049a8feabd94a1e54d1ee79c23d40c5e962d66c2255e6307833ae151'
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

## Live application follow-up

### transaction-concurrency | medium | replay refused concurrent Git drift after applying the reviewed bytes

Explicit apply used receipt `sha256:87b27c11bccb24e8da701ab61fec5df5936d6ab9606e3ee19f06e0f970b1ddbe` and crossed the mutation boundary. While its post-apply gates were running, commit `0f21eb73b41d092c5200921040f501bdb1a7b225` captured the exact `R100` rename. Replay subsequently detected the changed repository state and rolled the worktree back, demonstrating the fail-closed concurrency boundary. The resulting rollback residue was reconciled only after the restored old-path payload and the committed new-path payload both resolved to Git object `2aaa32a6f3c39606a18c12f506920e5a64a0ad99`, and no transaction marker remained.

### live-finding | low | reviewed finding is absent from the current audit inventory

The live `just audit-object-names --json` run scanned 62,585 declarations and reported 2,330 findings: 793 enforced and 1,537 advisory. Its expected exit code was 1 because the wider backlog remains. The selected finding `sha256:185e22d79ce6fa25f26b4d2086037944c305aa0b206078537c8fb89484b0f026` was absent. The canonical declaration `module:dev.registry.result_disposition_fragment_generator#binding=1` occurred once at `dev/registry/result_disposition_fragment_generator.py` with the rehearsed source hash `sha256:4eed2284f884c35c18242e230e88f45b350f792bccba10ac888741657414c6ad`; the retired source path and production references were absent.

### live-application-recommendation

Do not run Git commits or other repository-wide writers while an object-name transaction is active. Treat the transaction marker and the apply process handle as an exclusive operational window even though replay independently detects and refuses guarded-path drift.

### completion-snapshot | low | final live invariants remain satisfied

The completion audit inventory digest was `sha256:c7f4d3432cd739e93c270df6703f4210bf88871cfaca37b6e7f8b190dde44017` across 62,597 declarations. It reported 2,330 findings: 793 enforced and 1,537 advisory. The reviewed finding count was zero, the canonical declaration count was one, and the retired declaration count was zero. The old path was absent, the new path was present, and the transaction-marker count was zero. The audit target's exit code remained 1 solely because the repository-wide finding backlog is intentionally reported rather than suppressed.
