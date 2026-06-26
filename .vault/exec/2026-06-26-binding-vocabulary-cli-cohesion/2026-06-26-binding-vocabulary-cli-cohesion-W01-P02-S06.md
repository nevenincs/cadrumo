---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S06'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-vocabulary-cli-cohesion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Rename _sources.py to a corpus-catalogue module name (e.g. _corpus_catalogue.py) as one atomic relocation:corpus-catalogue commit and ## Scope

- `sweep verify_source_file / verify_source_catalogue at _validate.py`
- `the registry package __init__ re-export and __all__`
- `and the three test consumers`
- `run dev.docs.apidocs scaffold to regen the API-stub plus locale + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/domain/calculations/registry/_sources.py`
- `src/aeat/domain/calculations/registry/_validate.py`
- `src/aeat/domain/calculations/registry/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename _sources.py to a corpus-catalogue module name (e.g. _corpus_catalogue.py) as one atomic relocation:corpus-catalogue commit

## Scope

- `sweep verify_source_file / verify_source_catalogue at _validate.py`
- `the registry package __init__ re-export and __all__`
- `and the three test consumers`
- `run dev.docs.apidocs scaffold to regen the API-stub plus locale + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/domain/calculations/registry/_sources.py`
- `src/aeat/domain/calculations/registry/_validate.py`
- `src/aeat/domain/calculations/registry/__init__.py`

## Description

- Rename the registry BOE/AEAT corpus-catalogue integrity verifier file from the false-friend `_sources` to `_corpus_catalogue`; git records it as an 87 percent rename and clarify the module docstring to say it verifies corpus SourceReference files, not binding source kinds.
- Keep the public function names `verify_source_file` and `verify_source_catalogue` unchanged (they correctly verify corpus references).
- Sweep the `_validate` module-path import, the registry package `__init__` re-export (import line only; the `verify_source_*` `__all__` entries are function names and stay), and the three test-module imports.
- Run apidocs scaffold to remove the `_sources` stub, add the `_corpus_catalogue` stub, and swap the registry toctree entry.

## Outcome

Landed as one atomic commit `relocation:corpus-catalogue` (`fb681867a`). The `__all__` `verify_source_*` entries are function names and were intentionally left unchanged. collect-only clean (16461 baseline-equal), ruff clean (the four importer files needed their relocated import repositioned to its alphabetical slot, which ruff applied verifiably as the single own import move per file), and the 49 catalogue-verification / m145 / censo tests green.

## Notes

The registry `__init__` carried the same live peer WIP as S02 (the `casilla_metadata_alias` to `casilla_noncanonical_reference` rename). The B2 import swap was staged via the apply-cached own-only drive: HEAD-anchored own-only patch, `git apply --cached`, zero-foreign-marker verification, no-pathspec verified-index commit. The peer WIP was preserved (four `casilla_noncanonical_reference` occurrences still present post-commit). As with B1, the registry-package toctree `scaffold --check` staleness is peer-owned drift, not this B2 change.
