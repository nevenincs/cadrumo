---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:7b94a56b03ddcbd5e9eac0d63dcf079054c61332496b1ca6f5efb33e4bc40eb3'
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

# `source-casilla-integration` audit: `s42 inventory source ownership review`

## Scope

Independent review of S42 inventory caller-override ownership, single-home policy placement, selector-derived collision identity, equal and partial substitutions, alias refusal, undeclared manual behavior, and downstream binding boundaries.

## Findings

### s42-inventory-source-ownership-review | high | resolved planned target was not the ownership authority

`_calculate_input.py` parses values but does not own source precedence. The approved implementation uses the canonical `CALLER_OVERRIDE_PRECEDENCE_LADDER`; the calculation policy derives the lock set and the existing guard derives exact binding and casilla collisions from the revision. No second policy or hard-coded destination map was introduced.

### s42-inventory-source-ownership-review | medium | resolved lock-policy prose omitted promoted source families

The ladder and conformance documentation now describe deterministic inventory and annual-summary ownership alongside ledger and invoice families. The frozen conformance set matches the live declaration.

### s42-inventory-source-ownership-review | pass | collision refusal is complete and deterministic

Tests prove equal and different binding values refuse, one-, two-, and three-casilla substitutions refuse, semantic aliases fail before ownership matching, and replays retain typed value-free errors. Identical caller values do not receive a carve-out.

### s42-inventory-source-ownership-review | pass | undeclared manual behavior and downstream scope remain intact

A revision without inventory bindings keeps its manual casilla channel, proving the lock does not ban the numeric identifiers globally. S42 adds no inventory binding data, census connection claim, runtime repository composition, or CLI policy.

### s42-inventory-source-ownership-review | pass | final ownership policy is coherent

Independent review reported zero critical, high, medium, or low findings. Twenty-one focused tests, Ruff, the focused type checker, and diff hygiene were clean. Exploratory failures in stale IVA-selector and unrelated M349 tests were outside S42 ownership.

## Recommendations

Proceed to S43 and later binding work using the canonical inventory selector. Do not add a separate override map when real registry bindings replace the synthetic test revisions.
