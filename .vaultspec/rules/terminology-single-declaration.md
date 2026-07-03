---
name: terminology-single-declaration
---

# Terminology Single Declaration

## Rule

Every user-facing domain term must be enrolled once in the Terminology Handbook and referenced from docs through that entry; never redeclare an enrolled term's definition in prose or maintain a parallel hand-authored glossary.

## Why

The accepted `2026-06-10-docs-terminology-search-adr` identifies four unsynchronised terminology stores as the failure mode this feature removes. D7 makes the generated glossary and `:term:` references the enforcement surface, so inline redefinitions recreate the drift the Handbook exists to prevent.

## How

- Good: Add or update a concept fragment under `src/aeat/_data/terminology/concepts/`, then use `:term:` references in docs prose.
- Bad: Define "prorrata" in a how-to paragraph while also keeping a Handbook concept and generated glossary entry for `prorrata`.
