---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:91fb8fdbdf0e03ed738dad1690fc9b503a63bc3cea49824f8da7a9435bd006e5'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-s08-authority-gap-research]]"
---
# `aeat-export-fragment-generator-authority` audit: `S31 render profile formal review`

## Scope

This independent formal review covered only `dev/registry/_render_profile.py`, `dev/registry/tests/test_render_profile.py`, and the 128 authored fragments under `dev/registry/render_profiles/modelo_200/2025/`. It evaluated the accepted generator-authority ADR, plan step `W01.P02.S31`, the S08 authority-gap research, and the applicable fail-closed registry, no-legacy, quality-gate, RAG-discovery, and shared-worktree rules. The review was read-only for all implementation, test, and profile files.

The review specifically checked exhaustive literal membership; exact modelo, design-epoch, source-ref, and source-SHA identity; truthful separation of binary-resolved official-source evidence from exact-anchor reviewed policy; the 38 official smaller-field classifications; the 86 checkbox rules and their explicit `{0, 1}` selected/unselected policy; the `DP200DID` row 17 and row 20 final-two-digits year policy; semantic-kind and wire-shape consistency; dynamic exact-set proof; `DP200000` exclusion; absence of a legacy-tree oracle; absence of S32 renderer/provenance integration; test independence; and fragment reviewability.

## Findings

No critical, high, medium, or low findings were identified.

The compiled profile is bound to modelo `200`, design epoch `2025`, source ref `aeat-dr-200-2025`, and SHA-256 `a4506d24b7973a745d1225d59147078e03f14a30791a229d852b37f757442505`. Its governed set exactly equals the independently projected blank fixed numeric IR set: 3,323 unsigned `Num` width-17 anchors, 2,227 signed `N` width-17 anchors, and 126 individually authored smaller anchors. Validation rejects identity drift, duplicate or overlapping anchors, missing or unknown membership, type and width conflicts, official-content presence, and binary evidence drift in `validate_render_profile_authority` and `load_render_profile_source_evidence`.

The 126 smaller rules classify as 86 checkbox reviewed-policy decisions, two `DP200DID` final-two-digits year reviewed-policy decisions at rows 17 and 20, and 38 official-source conclusions. Every checkbox carries `allowed_values = ["0", "1"]`, `value_policy = "selected-1-unselected-0"`, and an exact governed anchor. Both short-year rules carry `value_policy = "four-digit-year-final-two-digits"` and exact governed anchors. The remaining 38 rules resolve their cited cell text from the hash-verified official workbook; manual semantic review found the declared year, month, day, enumeration, identifier, digit-string, percentage, integer, and date shapes consistent with their cited official descriptions or repeated-block format statements.

The real-source test derives eligibility from the bundled catalogue-selected parser IR and compares the profile's governed anchors to that dynamic exact set. It separately asserts the reviewed checkbox and short-year coordinate sets, verifies all other smaller rules use official-source evidence, proves `DP200000` remains a variable envelope outside eligibility, resolves evidence cells from the binary, and exercises source-cell, statement, and SHA mutations. The tests import production code directly and use no fake, mock, stub, patch, monkeypatch, skip, or xfail shortcuts. The AST no-legacy gate limits local dependencies to parser IR and semantic-map join, and the reviewed diff contains no export-tree or provenance integration belonging to S32.

All 128 fragments compile deterministically by filename and remain independently reviewable; the largest is 373 lines, below the asserted 500-line cap. Focused verification passed: 24 of 24 `test_render_profile.py` cases, Ruff on both Python files, and strict BasedPyright on both Python files with zero errors, warnings, or notes.

## Recommendations

Accept `W01.P02.S31` as passing formal review. Keep S32 integration out of this payload and execute it only in its separately reviewed plan step.
