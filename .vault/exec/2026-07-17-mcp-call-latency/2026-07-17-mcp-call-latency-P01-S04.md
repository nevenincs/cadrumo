---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace mcp-call-latency with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-07-17-mcp-call-latency-plan placeholders are machine-filled by
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
     The Pin the regression contract with real-behavior tests proving authority-boundary validation performs exactly one corpus-cache write, a direct RegistryValidator call performs zero, a verdict-cache hit skips validation including modelo list, and a fingerprint mismatch re-validates and ## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_validation_verdict_cache.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Pin the regression contract with real-behavior tests proving authority-boundary validation performs exactly one corpus-cache write, a direct RegistryValidator call performs zero, a verdict-cache hit skips validation including modelo list, and a fingerprint mismatch re-validates

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_validation_verdict_cache.py`

## Description

- Add a minimal real production observability counter `_DISK_CACHE_WRITE_COUNT` in `_validate_evidence.py`: incremented by every `_write_disk_cache` call and cleared by `reset_corpus_text_cache`, so the pin observes writes without any mock or monkeypatch.
- Add `test_validation_verdict_cache.py` with three real-behavior contracts over the bundled registry under isolated per-test corpus and verdict cache directories.
- Pin that a bare `RegistryValidator.validate_registry` performs zero corpus-cache writes (write count 0, dirty True, no cache file) while the authority boundary flushes exactly once cold (write count 1, dirty False, file present, verdict persisted).
- Pin that a verdict-cache hit skips validation: after deleting the corpus file and dropping in-process memos, a second construction does not re-extract (write count 0), does not recreate the corpus file, does not rewrite the verdict, and short-circuits the per-modelo `validate_modelo` path `modelo list` uses.
- Pin that a superseded stored verdict is deleted, re-validates in full (write count >= 1), and rewrites the verdict with the correct key that then certifies the tree on a fresh load.
- Bump the shared reviewability baseline for `_validate_evidence.py` from 360 to 362 to account for the counter.

## Outcome

The regression pin passes: three tests green in 20.8s serial. Diagnosed and closed a real cross-test isolation trap while writing them -- the registry validator memoizes results in a module-level cache keyed by `id(modelo)`, so a prior test's validation of the shared compiled modelos (from the `load_registry_tree` lru) short-circuited the source-citation reads the pin observes; the fix clears the compiled-tree lru in the reset helper so each construction gets fresh modelo objects.

`ruff check`, `ruff format --check`, and `ty check` are clean on the touched files; the reviewability line-budget gate stays green. Post-sidecar cold-versus-warm authority timing measured 10.75s (validate plus verdict write) against 0.89s (verdict-hit skip), a ~9.9s saving on the skipped path.

## Notes

The write counter is a legitimate additive observability hook in production code, not a test double: real writes increment it. It lands in `_validate_evidence.py`, which carries committed peer P02 work (S06 sidecar reader) but no uncommitted WIP, so the addition is safe; it adds no broad-exception handler and no import edge, so it does not touch the peer-owned gate failures on that file. The peer-owned full-tree gate failures (P02 `_validate_evidence`/corpus test, P04 `entrypoints/mcp` and `application/user_profile` lazy-import debt) remain outside this Step's surface and are reported to the coordinator, not fixed here. No incidents; no scaffolds left in code.
