---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:482db6fda67480317334e0e5e6d5bb8fbb3bc9a40f8478570083d101fd200259'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
  - "[[2026-08-05-ci-lane-deconflation-P02-S68]]"
---

# `ci-lane-deconflation` audit: `P02.S68 code review`

## Scope

Independent review of the `P02.S68` end-to-end change chain: `ef94186c89`,
`f2ac6af8f6`, `058419f887`, and `569c35f2f9`. Reviewed the S68 and still-open
S69 plan contracts, S68 execution evidence, the official Modelo 296 2024
record design and its provenance, semantic-map loader and render transport,
the published generated fragments and manifest, production record parsing,
and the parser and export-layout ratchet tests.

## Findings

No S68 findings. The official `aeat-dr-296-2024` design expressly describes
the primary perceptor's position 500 as `BLANCO`; the three rival Tipo-2
design sheets instead require `F`, `A`, and `B`. The reviewed mapping carries
only that authoritative blankness fact as the existing strict
`RecordDiscriminator(offset=500, length=1, requires="blank")`. The typed
semantic-map model, strict provenance normalizer, render path, generated M296
fragment, and production parser preserve the same rule without a parallel
vocabulary or an unproven optional-field assumption.

The parser test exercises all four real published records at byte 500 and
selects exactly one record for each `BLANCO`/`F`/`A`/`B` alternative. It is
therefore a primary-versus-rival proof rather than a synthetic discriminator
unit test. The join-ratchet inventory is empty only because the same generated
declaration reaches the production coverage join.

No S69 mechanism was introduced. `record_identity` remains the pre-existing
parser/source anchor; this change transports only the already-established
runtime discriminator. S69 remains open for its proposed non-runtime,
authored identity mechanism and must not be inferred closed from this review.

Focused validation produced 81 passes and two failures in import-surface
assertions: `test_renderer_module_has_no_old_tree_or_approximate_admission_surface`
and `test_public_loader_has_one_toml_parser_owner`. Both are pre-S68 drift:
their observed imports were introduced by the 2026-08-26 registry public-module
relocation, while S68 adds only `RecordDiscriminator` transport. They do not
affect the reviewed S68 behaviour, but leave that separate structural-test
debt visible.

## Recommendations

Approve `P02.S68`. Keep `P02.S69` open and do not substitute a new
`record_identity` transport for its required ADR-grade decision. Repair the
two stale import-surface assertions under their public-module relocation owner;
do not weaken or omit them from the S68 validation record.
