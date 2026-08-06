---
name: terminology-scaffold-preserve-contract
trigger: always_on
---

# Terminology Scaffold Preserve Contract

## Rule

Every Terminology Handbook scaffold run must preserve curated fields verbatim, scaffold new entries as empty drafts, and retire vanished entries as tombstones with `replaced_by`; never fuzzy-fill curation fields or delete concept records.

## Why

The accepted `2026-06-10-docs-terminology-search-adr` adopts the msgmerge three-outcome contract in D3 because generated discovery and human curation share the same TOML authoring tree. Clobbering curated prose, inventing definitions, or deleting vanished records breaks reviewability and the immutable-id/tombstone model.

## How

- Good: A new registry enrolment creates a draft concept with empty curated prose, while an existing concept keeps its hand-edited definitions and aliases unchanged.
- Bad: A scaffold run rewrites a curated short description from source labels, guesses an English definition, or removes a concept file because the source disappeared.
