---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:ffa8abc201a9b61febb15b33bf0c32da400314343c695467d4aac70a7600cccf'
step_id: 'S03'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Introduce lightweight node-attached command execution policy and expose it through the live command census

## Scope

- `src/cadrumo/entrypoints/cli/_command_policy.py and _command_suggestions.py`

## Description

Introduce an immutable, import-light command execution policy composed with the
closed capability, side-effect, and performance taxonomy.

Carry destructive, filing-handoff, live-write, and storage-route judgments on
the callback-owned record, with cross-axis validation that rejects authority,
effect, route, and runtime-type contradictions.

Attach policy metadata through an order-independent decorator that returns the
original callback and refuses a second contradictory declaration.

Expose callback policy directly on each immutable live command node while
preserving honest `None` for unannotated callbacks and non-executing groups.

Exercise real eager and lazy Typer registrations, both decorator orders,
executable and non-executing groups, handler identity, corrupt metadata,
contradiction branches, and a same-path callback-policy anti-tautology.

## Outcome

The live census now carries one callback-owned `CommandExecutionPolicy` or an
explicitly absent value. It performs no path-table join and invents no safe
default, so the later universal enrollment gate can detect every unmigrated
root, group, and leaf.

The policy seam is ready for the atomic subtree migrations without moving the
legacy risk or profile-write catalogues prematurely. Focused Ruff and `ty`
checks pass, and the combined capability, policy, and command-census suite
passes 35 tests.

## Notes

Semantic discovery used the required targeted-source fallback because the
installed `vaultspec-rag` client refused the newer running daemon. The first
mandatory review identified cross-axis under-declaration and runtime-type gaps;
both were corrected before re-review. Peer-owned worktree changes were left
untouched.
