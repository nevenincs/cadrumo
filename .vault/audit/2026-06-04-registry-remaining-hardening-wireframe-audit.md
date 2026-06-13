---
tags:
  - '#audit'
  - '#registry-hardening-next-work'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
---

# `registry-hardening-next-work` audit: `remaining hardening execution wireframe`

## Purpose

Persist the remaining, previously ignored, or explicitly out-of-scope registry
and schema-hardening directions as a sequential execution wireframe. This is a
work queue map, not authorisation to implement every item in this plan.

## Sequential wireframe

1. **Legal/source grounding gate**
   - Require every modelo definition change to resolve legal refs, source refs,
     and official setup evidence.
   - Completion signal: step records name the legal/source backing and registry
     gate used.
   - Current state: W07 covers the M200/M303 completeness repairs.

2. **Generic schema and loader contract**
   - Verify revision/fragment support is generic across modelos and not
     implemented as M100/M200 special cases.
   - ADR need: only if import topology or schema semantics change.
   - Completion signal: tests exercise fragmented and non-fragmented revisions
     through the same schema/load path.

3. **Registry drift validators**
   - Keep cross-revision casilla drift, completeness drift, source-kind,
     row-size, and file-size gates active.
   - Next work: identify gaps where a validator is advisory but should become
     blocking.
   - Completion signal: failing synthetic mutation or real-corpus drift is
     caught by `RegistryValidationError` or a committed registry test.

4. **Fragment rollout pressure**
   - Audit remaining large single-file or near-threshold TOML artifacts.
   - Split only when reviewability pressure is real; preserve schema semantics.
   - Completion signal: no committed TOML file trends back toward monolithic
     review hazards, and reviewability gates remain below cap.

5. **M100 revision/fragments compatibility**
   - Re-audit M100 after generic fragmentation support changes.
   - Ensure M100 is not relying on accidental special casing from the first
     split campaign.
   - Completion signal: M100 revision suites and directory-mode loader tests
     pass without per-modelo logic.

6. **Official modelo setup verification**
   - For calculation-bearing modelos, require real registry snapshot/load plus
     record-design/export/completeness checks before accepting data edits.
   - Completion signal: model-specific step records include official setup
     evidence or explicitly document why no record-design source exists.

7. **Monolithic module decomposition**
   - Continue audit-first extraction for large registry modules.
   - Priority order: `_schema.py`, `_record_design.py`, `_bindings.py`,
     `_formula_runtime.py`, and public export barrels.
   - ADR need: required for schema import-topology changes; optional for pure
     helper extraction that preserves public interfaces.

8. **Vault closure discipline**
   - Every new edge gets a plan step, step record, audit or review record, and
     path-scoped commit.
   - Completion signal: no known red or exception remains only in chat.

## Next-slice recommendation

The next executable slice should be the generic schema/loader contract audit:
prove the current revision and fragment constructs are cross-modelo, then decide
whether any schema import-topology split requires an ADR before implementation.
