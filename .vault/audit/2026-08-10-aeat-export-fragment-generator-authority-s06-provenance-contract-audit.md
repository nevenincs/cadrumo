---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:ae6bc591409bece4ae02bae87ffdc64c26edd964e49153c757c730e2f35b48ff'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `s06 provenance contract`

## Scope

Audit W01.P02.S06's development-only provenance contract. The review covered canonical serialisation, source and semantic-map attestation, path/file-digest refusal, schema-version fail-closed behaviour, and the boundary that excludes legacy export layouts from inputs and fallbacks.

## Findings

No critical, high, or medium findings remain. Independent review confirmed that the manifest uses the repository canonical JSON and SHA-256 helpers, records the exact source, map, target, parser, generator, loader-semantics, and output-file evidence, and rejects noncanonical, ambiguous, unsafe, and stale shapes before they can attest to a generated tree.

## Recommendations

W02 publication must obtain the loader-materialised target layout only after the freshly generated tree has passed its real loader validation, then write this sibling manifest atomically with that tree. Do not add a legacy-tree lookup, compatibility fallback, or timestamp field.
