---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
step_id: 'S05'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Add a settings-derived corpus-text cache location, rename the cache file to the cadrumo stem, and remove the hard-coded gettempdir path

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_evidence.py`

## Description

- Add a `cadrumo_corpus_text_cache_dir` Settings field and enroll it in the state-root derivation table at `cache/corpus-text`, plus the repo-relative-path normalise tuple and the env template.
- In `_validate_evidence.py`, resolve the cache path from that setting (`_corpus_text_cache_path`), rename the file `aeat_corpus_text_cache.json` to `cadrumo_corpus_text_cache.json`, and remove the hard-coded `tempfile.gettempdir()` location.
- Make the write path create the derived directory and read-merge any concurrent on-disk entries before the atomic `os.replace`, so a parallel writer's key is not dropped.
- Upgrade the unreadable-cache read log from debug to warning so the silent-degrade-to-miss becomes observable while preserving the miss behavior.
- Add a `reset_corpus_text_cache` test-isolation helper and a real-behavior test asserting the derived location, the new filename, a write/read roundtrip, and the concurrent-merge behavior.
- Regenerate `docs/reference/environment-overrides.md` for the new field.

## Outcome

The corpus source-text validation cache now lives at `<cadrumo_local_storage_root>/cache/corpus-text/cadrumo_corpus_text_cache.json`, scoped per user by construction, closing the shared-host clobber hazard of the former fixed OS-temp-dir name. Gates: the focused corpus-cache suite, the whole-table state-root derivation test (now covering the new field), the settings/env-parity suite, and the env-reference freshness gate all pass; ruff clean; collection clean repo-wide.

Residual multi-process hazard (documented): the atomic replace prevents a torn file, and the read-merge narrows lost updates, but two writers merging the same pre-image can still drop one's key. This only costs a recompute, never a wrong value, because each cache key embeds the source file's size and mtime, so a stale entry can never match a changed file.

## Notes

The full registry suite run alongside this Step reported failures, all owner-triaged as OUTSIDE this Step's surface and pre-existing on the branch: they are registry-DATA assertions (Modelo 210 completeness-vs-closure legal-ref mismatch on `trlirnr-rdleg-5-2004:art-13.1`, Modelo 100 estimacion-objetiva agraria rendimiento values, and a bundled-normative-corpus inventory check on `ley-37-1992.json`). This Step's commit touched only the settings field, the corpus-cache module, the env template, the generated env doc, and a new test - no registry TOML, no completeness manifest, no corpus binaries - so it cannot affect those data assertions; registry LOAD itself is healthy (2909 passed), and git history shows the last edits to that registry data were peer commits, not this Step. The failures re-ran identically under `-n 0` (sequential), confirming they are not the loader-cache parallel race.
