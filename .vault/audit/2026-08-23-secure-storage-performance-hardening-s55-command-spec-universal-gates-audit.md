---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:b78a453cdf83395ecdd821853e52519aba269b744a9b4e1bf5186e99b7dfe97c'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
  - "[[2026-08-23-secure-storage-performance-hardening-command-spec-authority-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace secure-storage-performance-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `secure-storage-performance-hardening` audit: `S55 CommandSpec universal gate review`

## Scope

Audit the S55 universal authority gates against the accepted production-authored `CommandSpec` decision. The review covers detector independence, complete current/future field traversal, distributed-module enrollment, exact deferred-target resolution, legacy-authority absence, and planted negative controls.

## Findings

### former-authority-detector | high | Direct structural declarations could evade the first AST gate

The first detector rejected named legacy registrars and artifacts but accepted direct Typer construction, command decorators, registrar function families, add-command calls, and command path mirrors. The gate was expanded with structural AST classification and independently planted examples for every shape. It also exposed and removed the dormant `OutputLanguageOpt` Typer declaration.

### deferred-target-resolution | high | Module-only checks did not prove public executable symbols

The first target gate used module discovery only, so a missing, private, or wrong-kind qualname inside an existing module could pass. The corrected gate resolves every dotted public qualname, requires callable handlers, requires model-schema target types, and proves missing-module, missing-symbol, private-symbol, and wrong-kind controls.

### distributed-enrollment | high | Aggregate-to-graph equality was circular

The first exact-set test compared a tuple with a graph constructed directly from that tuple. The corrected development gate independently discovers all production `*_command_specs.py` modules, follows the aggregate's import edges, and proves an omitted planted module is detected.

### translation-key-traversal | medium | Confirmation prompt keys were omitted

The first explicit field list did not traverse `confirmation_prompt_key`. The corrected detector recursively walks immutable dataclass fields, so every current and future `TranslationKey` field is enrolled without another maintained field list.

## Recommendations

- Keep production runtime consumers on the immutable graph; retain filesystem discovery strictly as a development/release gate.
- Require a planted control whenever the forbidden-authority classifier grows a new structural shape.
- Keep deferred targets public and importable, and keep every operator-facing string represented by an authored locale key.
