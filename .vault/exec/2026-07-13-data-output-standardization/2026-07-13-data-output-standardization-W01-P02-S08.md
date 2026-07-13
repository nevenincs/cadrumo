---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S08'
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
     The S08 and 2026-07-13-data-output-standardization-plan placeholders are machine-filled by
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
     The Update the white-box registry-cache and authority tests for the relocated cache locations and ## Scope

- `src/cadrumo/domain/calculations/registry/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update the white-box registry-cache and authority tests for the relocated cache locations

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Description

- Point the stale-authority-cache regression in the authority test at the real `registry_disk_cache_dir()` location (with the renamed `cadrumo_registry_` stem) instead of a raw `tempfile.gettempdir()` path, and drop the now-unused `tempfile` import.
- Extract a pure `_resolve_registry_disk_cache_dir` helper in `_loader_cache.py` so the three resolution branches (explicit override, pytest host-shared temp, production storage-root derivation) are exercised with real inputs rather than by manipulating the ambient process.
- Add a relocated-defaults test covering the pure resolver's three branches plus the live accessor under pytest.
- The pickle-name glob/docstrings in the loader-cache isolation test were already swept with the rename in the S06 commit (relocation-atomicity); the eviction real-behavior test landed with the S07 code.

## Outcome

The white-box cache and authority tests now assert against the relocated registry cache location and the renamed pickle stem, and the relocated-default derivation is covered by real-input tests. Gates: the loader-cache isolation suite, the eviction suite, the relocated-defaults suite, and the full authority suite are 28 passed under sequential (`-n 0`) re-run; ruff clean.

## Notes

The full registry suite still carries the pre-existing peer-owned registry-DATA failures triaged from S05 onward (Modelo 210 completeness-vs-closure legal-ref mismatch on `trlirnr-rdleg-5-2004:art-13.1`, Modelo 100 estimacion-objetiva agraria rendimiento, and a bundled-normative-corpus inventory check on `ley-37-1992.json`). This phase (W01.P02) changed only cache file locations/names and added a settings field + eviction; it touches no registry TOML, completeness manifest, or corpus binary, so those data failures are unrelated and unchanged. Registry LOAD is healthy across the suite.
