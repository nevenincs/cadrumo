---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-06'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S460-001 | HIGH | Recovery verification errors suggested the wrong custody verb

`RecoveryVerificationError` defaulted to `aeat config verify-recovery --recovery-key <WORDS>` even when the failing path was `config recover`. S460 now routes the error registry suggestion to `aeat config recover --recovery-key <WORDS>` and pins the rendered envelope suggestion in recovery-facade coverage.

Status: resolved in S460.

## S455-001 | LOW | Declaration full-boundary corpus was not rerun as one module

S455 changes declaration provenance construction while preserving the existing extraction path for on-disk PDFs. A targeted real corpus declaration parse passed, and the broad declaration boundary module timed out when batched with other focused modules.

Status: accepted for S455. The changed declaration behavior is covered by `test_parser_extracts_legal_entity_nif_from_pdf`, while the full declaration corpus remains expensive and should be run in a longer gate when the inbound campaign batch closes.

## S455-002 | INFO | Inbound parser provenance path review passed

Review checked the S455 diff for local path leakage in successful parser records, the justificante successful dispatch cache, and borrador unrecognised artefact errors. The implementation keeps real file paths only at extraction time and persists digest-derived `.secure-source/<sha256>.pdf` references in parser records.

Status: no action required.

## S460-002 | MEDIUM | Operator-surface contract under-declared root custody verbs

The accepted operator-surface contract only declared `config unlock` while the CLI mounted first-class `config lock`, `config unlock`, `config rekey`, `config recover`, `config show-recovery`, and `config verify-recovery`. S460 now adds an explicit custody domain and mounted command-family rows for each root-level custody child.

Status: resolved in S460.

## S460-003 | LOW | Root-fallback recovery-path coverage still exercised profile switch

The root-fallback real-entrypoint regression continued to exercise `config profile switch` after the static policy table moved to `config unlock`. S460 updates the real-entrypoint regression to drive `config unlock` so the canonical recovery path remains guarded against root-fallback write-policy refusal.

Status: resolved in S460.
