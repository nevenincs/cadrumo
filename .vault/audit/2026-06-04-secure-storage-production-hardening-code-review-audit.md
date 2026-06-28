---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S294]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S383]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S384]]'
---

# `secure-storage-production-hardening` Code Review

## SSH-CR-001 | PASS | Registry enrollment is enforceable

The reviewed diff registers modelo projection, comparison, selector, and work-addressing exception families with stable `ErrorCode` metadata. `test_registry_enforcement.py` passes after importing the codebase, which protects against orphan registry rows and unregistered `AeatError` subclasses.

## SSH-CR-002 | PASS | Localized refusal messages retain legal grounding

The Modelo 210 and Modelo 721 refusal messages were restored to include the legal anchors required by the regression tests (`G320` / AEAT Sede and `HFP/887/2023` / threshold), using `python -m aeat.locales` rather than hand edits.

## SSH-CR-003 | PASS | Silent best-effort fallbacks now log at debug level

Best-effort CLI enrichment paths now emit debug logs with `exc_info=True` before falling back. The remaining broad catch in active-bucket conversion re-raises as a typed Typer boundary error rather than swallowing the root cause.

## SSH-CR-004 | PASS | New split-out files are tracked as pending AFR rows

The commit includes split-out modelo modules that were already wired into tracked application and CLI surfaces. The plan now carries pending `AFR-294` through `AFR-301` rows for those new production files so future work can close them one-file-per-row instead of relying on this cross-commit note.
