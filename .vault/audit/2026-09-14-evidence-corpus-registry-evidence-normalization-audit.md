---
tags:
  - '#audit'
  - '#evidence-corpus'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:6d1ac52ff136bcf7d4533437c9a67f0ae60f574820d0e975e9e6c260644f9f53'
related:
  - "[[2026-09-14-evidence-corpus-ownership-reference]]"
---
# `evidence-corpus` audit: `registry evidence normalization`

## Scope

Review the evidence corpus and registry normalization work: source-bound PDF annotations, BOE XML routing and direct grounding, removal of redundant derivatives and orphan captures, acquisition suffix contracts, source-evidence receipt stability, package boundaries, and the quality gates used to measure completeness.

## Findings

### registry-evidence-normalization | high | published authority cites retired overlays

The published authority still contains legal locators ending in `source.pdf.extracted.md#anchor` after those authored overlay files were removed. `test_no_committed_legal_entry_cites_a_fused_redaction_history` fails at `andalucia-ley-5-2021:art-23-bis`, so the source registry and published authority are not yet synchronized.

### registry-evidence-normalization | medium | manual annotation validation is incomplete

`verify_manual_annotation_catalogue` checks basic annotation shape but does not bind an annotation to the sibling extraction/source digest, prove every declared page exists exactly once, or resolve every selector against the extraction. Anchor validation also admits leading `#`, surrounding whitespace, and other noncanonical values. An unused or stale annotation can therefore pass catalogue validation while being uncitable.

### registry-evidence-normalization | resolved | Git state was used as a quality oracle

Wheel parity, source coverage, header-key naming, and a combined-period campaign gate derived completeness from `git ls-files`, `git grep`, or direct `.git/index` parsing. Their results changed with staging and commit state rather than product policy. Current gates now enumerate the repository-visible source tree in-process; the noisy combined-period campaign gate and history-dependent revision round-trip campaign suite were retired.

## Recommendations

- Republish the authority from the normalized source registry after concurrent registry writers settle, then rerun the fused-redaction refusal and authority round-trip gates.
- Strengthen manual annotation validation to bind source and extraction identities, require unique existing pages, enforce canonical anchor syntax, and prove every selector resolves.
- Keep Git outside quality, completeness, parity, and packaging oracles. Use `dev.source_tree.repository_files` plus the owning inclusion/exclusion, catalogue, or schema policy. Git remains valid only where commit identity or Git behavior is itself the explicit workflow subject.
