---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S07'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace service-capabilities with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-06-15-service-capabilities-plan placeholders are machine-filled by
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
     The Probe Ollama before vision inference + refuse instructively and ## Scope

- `widen classify CLI to catch LLMProviderError/connection errors`
- `add ollama providers row`
- `Playwright hint`
- `src/aeat/application/ledger`
- `src/aeat/entrypoints/cli` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Probe Ollama before vision inference + refuse instructively

## Scope

- `widen classify CLI to catch LLMProviderError/connection errors`
- `add ollama providers row`
- `Playwright hint`
- `src/aeat/application/ledger`
- `src/aeat/entrypoints/cli`

## Description

- Wrap the on-host vision inference so an unreachable Ollama / unpulled model becomes a typed LLMClassifierError (which the classify CLI already renders) carrying the exact remediation, instead of a raw httpx.ConnectError traceback; real-behaviour test.

## Outcome

classify --read-evidence with Ollama down/model-missing now refuses instructively.

## Notes

The ollama row on `ledger providers` and the Playwright BrowserError remediation hint are subsumed by `config check` and deferred as minor.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
