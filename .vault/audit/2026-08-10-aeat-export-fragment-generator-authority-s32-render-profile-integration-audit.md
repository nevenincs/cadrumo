---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:ce6e41ad445af504bd755b569bcb1da6469e089ab540044b6482ceb5b56f9765'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-s31-render-profile-audit]]"
---
# `aeat-export-fragment-generator-authority` audit: `s32 render profile integration`

## Scope

Verdict: **PASS. No open critical, high, medium, or low findings remain.**

This independent formal review covered approved plan step `W02.P03.S32` against the accepted generator-authority ADR and fixed-width amendment, the active plan, render-profile research, and the S31, S37, S38, S40, and S41 execution and audit evidence. Production scope was `dev/registry/_export_tree.py`, `_render_profile.py`, `_provenance_manifest.py`, `_generated_tree_validation.py`, `_generated_tree_publication.py`, and `_generated_tree_check.py`; the corresponding focused tests and variable-envelope gate were reviewed directly. The adjacent canonical `CasillaId` import moves in parity modules and the peer-owned `is_link_like` relocations were inspected for boundary contamination and did not create an S32 authority duplicate or semantic regression.

The final generation path validates the exact `RenderProfile` and `RenderProfileSourceEvidence` before target creation, refuses variable envelopes before rendering, preserves nonblank official numeric facts, consults the profile only for blank numeric exact anchors, maps all eleven public `ExportValuePolicy` members exhaustively, preserves allowed values only for enumerated digits, and uses the public domain schema and sole runtime codec. `ExportTreeTransportProfile` is transport-only and the retired `ExportRenderProfile` name has no alias. The canonical order-independent profile digest includes design identity, fragment membership, width and singleton rules, exact anchors, allowed values, policy and official evidence, plus independently resolved source-evidence facts. Provenance schema version 2 and generator/normalization version cutovers carry the profile schema and digest through emit, load, validation, recovery, check, and publication verification.

Reviewed tests import production directly and use no fake, mock, stub, patch, monkeypatch, skip, or xfail shortcuts. Independent final verification passed the three exact interrupted-recovery cases, including separate profile and evidence drift, and all 165 tests in `dev/registry/tests`. Ruff over `dev/registry` passed. Strict BasedPyright over all reviewed production modules reported zero errors, warnings, or notes.

## Findings

### publication-recovery-authority-bypass | high | Interrupted publication could finalize stale profile provenance

The initial review found `publish_validated_generated_export_tree` invoking `_recover_interrupted_publication` before normal current-authority validation. Recovery received only paths and context and could accept a journal-matching package without comparing its profile provenance to the joined design, semantic map, rendered derivations, current profile, or current source evidence. A candidate validated under authority A could therefore be finalized by a retry supplying authority B.

Resolution: **RESOLVED.** Recovery now requires every current generation authority. `_verify_recovery_package_against_current_authorities` loads the exact recovered layout, requires equality with the current rendered layout, and calls the canonical `verify_export_fragment_provenance_manifest` with the current joined design, semantic map, target, rendered derivations, render profile, and source evidence. This verification occurs before accepting an already-cut-over target, before moving a staged candidate into the target, and before deleting rollback material or finalizing the journal.

Real `candidate_live` interruption tests independently mutate the profile fragment authority and source-evidence identity. Both refuse while preserving the live target bytes, retained rollback bytes, and journal bytes, with no candidate-path resurrection. The unchanged-authority recovery case continues to complete successfully. Independent execution passed all three exact recovery cases.

## Recommendations

Accept `W02.P03.S32` as passing formal review. Preserve current-authority verification at every recovery success transition, the single public policy and codec owners, exhaustive mapper coverage, exact-anchor-only profile projection, order-independent complete profile digest, profile-bearing provenance hard cutover, variable-envelope refusal, and the real no-mutation recovery regressions.
