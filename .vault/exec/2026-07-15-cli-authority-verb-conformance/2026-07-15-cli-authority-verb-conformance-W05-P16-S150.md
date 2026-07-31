---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:81553cdf4828cc43383e65fd2cad6f134469234f744701e189de75e195d26344'
step_id: 'S150'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove suggestions resolve only to accepted registered commands

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_suggestion_command_conformance.py`

## Description

- Read the suggestion-conformance gate and establish which surfaces it resolves.
- Confirm it carries proof that its scanner is not vacuous.
- Run it.

## Outcome

The named gate proves suggestions resolve only to accepted registered commands, and its coverage is wider than the row implies. It walks the real Click tree with no mocks or fixture trees and resolves citations from the registered error suggestions, the curated operator help documents, every AST-extracted string literal in the adapters, application, core error, and entrypoint packages, and all four locale catalogues.

That literal sweep is what brings the next-action builders, write-policy strings, and envelope-builder strings under enforcement, and AST extraction means a commented-out citation cannot false-positive. The gate carries four proofs that its scanner bites: it flags a dead citation, a citation that terminates on a group, a dead option citation, and the three real locale-divergent defects it closed when it landed.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
