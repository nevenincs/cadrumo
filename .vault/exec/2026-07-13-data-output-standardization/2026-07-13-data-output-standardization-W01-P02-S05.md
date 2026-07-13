---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S05'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace data-output-standardization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-07-13-data-output-standardization-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Add a settings-derived corpus-text cache location, rename the cache file to the cadrumo stem, and remove the hard-coded gettempdir path and ## Scope

- `src/cadrumo/domain/calculations/registry/_validate_evidence.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
