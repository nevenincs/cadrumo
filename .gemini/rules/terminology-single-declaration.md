---
name: terminology-single-declaration
trigger: always_on
---

# Terminology Handbook: one declaration, preserved by scaffold

## One declaration

Every user-facing domain term is enrolled once in the Terminology Handbook and
referenced from docs through that entry. Never redeclare an enrolled term's
definition in prose, and never maintain a parallel hand-authored glossary — four
unsynchronised terminology stores were the failure mode the Handbook removes.

## How

- **Good:** add or update a concept fragment under
  `src/cadrumo/_data/terminology/concepts/`, then use `:term:` references in docs
  prose.
- **Bad:** defining a term in a how-to paragraph while a Handbook concept and a
  generated glossary entry for it also exist.

## Scaffold preserves, never clobbers

Every scaffold run must preserve curated fields verbatim, scaffold new entries as
**empty drafts**, and retire vanished entries as **tombstones** with
`replaced_by`. Generated discovery and human curation share the same TOML
authoring tree, so clobbering curated prose, inventing definitions, or deleting
vanished records breaks reviewability and the immutable-id model.

## How

- **Good:** a new registry enrolment creates a draft concept with empty curated
  prose, while an existing concept keeps its hand-edited definitions and aliases
  unchanged.
- **Bad:** a scaffold run rewriting a curated description from source labels,
  guessing a definition, or removing a concept file because the source
  disappeared.

Source: ADR `2026-06-10-docs-terminology-search-adr` (D3, D7). Companion:
`glossary-concepts-are-taxpayer-facing`.
