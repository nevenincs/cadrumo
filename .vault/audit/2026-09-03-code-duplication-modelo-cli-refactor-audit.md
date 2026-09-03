---
tags:
  - '#audit'
  - '#code-duplication'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:f37f6b58216b47c3271ce75c487cf429d3878557aed573aca54bdac763b4f242'
related:
  - '[[2026-06-01-semantic-cluster-hardening-adr]]'
  - '[[2026-08-23-secure-storage-performance-hardening-command-spec-authority-adr]]'
---
# `code-duplication` audit: `Modelo CLI common parameter refactor review`

## Scope

Reviewed the committed CLI sequence `76d79285cc` and `9abd7620bd`. The review covered the frozen selector and filing-election `OptionSpec` tuples; `modelo export` and `modelo review-package build` ordering, defaults, declarations, help metadata, requiredness, and parser materialization; cross-module helper visibility and type safety; and the retained export/review command-signature overlap.

## Findings

### command-contract | low | No command-spec regression detected

The six selector options and three filing-election options preserve their prior names, declarations, deferred value targets, literal defaults, translation keys, multiplicity, flag configuration, and empty constraints. They are spliced at their original offsets in both command specifications, preserving order and leaving the surrounding `work_unit_id`, `output`, `revision`, `actor`, and `notes` contracts unchanged.

### immutable-identity | low | Shared options are immutable and retain exact identity

The shared collections are tuples of frozen `OptionSpec` records. Both command specifications use the same object identities for every shared selector and filing-election option, so later authority changes have one canonical declaration without shared mutable state.

### helper-boundaries | low | Public in-package helper sharing is intentional

`export_modelo_revision_for_cli` is the single draft-export boundary used by the standalone export and review-package builder. The review builder retains its broader command signature because it resolves the revision and owns package-only output and `notes`; it delegates draft creation once rather than cloning export behavior. `resolve_modelo_work_unit_for_wizard` similarly centralizes the work and amendment wizard target-resolution path, while the frozen amendment target transports the same six coordinates.

### validation | low | Focused authority and type checks pass

The focused non-work command-spec suite passed all 11 tests, including exact tuple identity, order, defaults, help keys, public target resolution, and runtime materialization. Ruff and ty passed on every changed CLI module. The committed diff also passes whitespace validation.

## Recommendations

No follow-up action is required. Keep the two shared tuple exports as the sole structural authority for these nine repeated option declarations, and extend their focused identity-and-order test if another command consumes either group.
