---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:a69783adf7bb44d6aec8fc52c498abbf258996c7493c0b030fa23459e8c25a54'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
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

# `source-casilla-integration` audit: `s39 inventory resolver review`

## Scope

Independent review of S39 repository resolution, projection reuse, source provenance, diagnostic taxonomy, encrypted corruption handling, confidentiality, and downstream enrollment boundaries.

## Findings

### s39-inventory-resolver-review | high | resolved diagnostics collapsed distinct failure states

The resolver now emits closed machine reasons for unsupported context, invalid selector, absent ledger, unreadable storage, incomplete or tampered projection, and retained source conflict. Messages remain value-free and do not require prose parsing.

### s39-inventory-resolver-review | high | resolved provenance omitted the sealed projection identity

Calculation provenance now uses the canonical projection fingerprint, which commits the source-ledger fingerprint together with the projected values and authority provenance. Determinism and semantic-change tests prevent regression to the narrower ledger fingerprint.

### s39-inventory-resolver-review | high | resolved encrypted corruption escaped the repository contract

Strict schema-v3 rehydration failures are translated by `InventoryLedgerRepository.load` into `InventoryLedgerError`; the application resolver depends only on that canonical contract. The safe error is raised after leaving the exception handler so both cause and context are absent.

### s39-inventory-resolver-review | high | resolved protected facts remained reachable through exception chaining

Real encrypted corruption coverage scans the formatted error, diagnostics, and logs for every fixture evidence reference and digest plus actor, command, and monetary canaries. It also proves the safe public error retains neither the raw validation cause nor context.

### s39-inventory-resolver-review | medium | resolved fake-only coverage masked adapter behavior

The focused suite now exercises real encrypted absence, complete success, and corrupted required authority state in addition to deterministic identity, semantic mutation, continuity tamper, retained conflict, unsupported coordinates, and allocation-free no-binding behavior.

### s39-inventory-resolver-review | medium | resolved modelo identity bypassed canonical vocabulary

The resolver compares against `Modelo.M100`. The repository-wide vocabulary sentinel reports no S39 offender; its remaining four findings belong to unrelated concurrent files.

### s39-inventory-resolver-review | pass | final resolver contract is coherent

Both independent final reviews reported zero critical, high, medium, or low findings. Thirteen focused tests, Ruff, the type checker, scoped diff hygiene, and feature vault validation were clean.

## Recommendations

Proceed to S40 by enrolling this resolver and updating the explicit inventory source disposition. Do not duplicate projection arithmetic, weaken the encrypted repository error boundary, or claim connected status before the resolver is present in the production mesh.
